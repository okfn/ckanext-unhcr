import copy
import datetime
import json
import logging
import requests
from urlparse import urljoin
from dateutil.parser import parse as parse_date
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import aliased
from ckan import model
from ckan.authz import has_user_permission_for_group_or_org
from ckan.plugins import toolkit
from ckan.lib import mailer as core_mailer
from ckan.lib.mailer import MailerException
import ckan.lib.plugins as lib_plugins
from ckan.lib.search import index_for, commit
import ckan.logic as core_logic
import ckan.logic.action.get as get_core
import ckan.logic.action.create as create_core
import ckan.logic.action.delete as delete_core
import ckan.logic.action.update as update_core
import ckan.logic.action.patch as patch_core
#import ckan.lib.activity_streams as activity_streams
import ckan.lib.dictization.model_dictize as model_dictize
from ckanext.unhcr import helpers, mailer, utils
from ckanext.unhcr.models import AccessRequest
from ckanext.scheming.helpers import scheming_get_dataset_schema

log = logging.getLogger(__name__)


def _get_user_obj(context):
    if 'user_obj' in context:
        return context['user_obj']
    user = context.get('user')
    m = context.get('model', model)
    user_obj = m.User.get(user)
    if not user_obj:
        raise toolkit.ObjectNotFound("User not found")
    return user_obj


# Package

def package_update(context, data_dict):
    notify = False
    if not context.get('ignore_auth'):
        user_obj = _get_user_obj(context)
        # Decide if we need notification
        # - deposited-datset AND
        # - not a test env AND
        # - just published
        if data_dict.get('type') == 'deposited-dataset' and hasattr(user_obj, 'id'):
            dataset = toolkit.get_action('package_show')(context, {'id': data_dict['id']})
            if dataset.get('state') == 'draft' and data_dict.get('state') == 'active':
                notify = True

    # Update dataset
    dataset = update_core.package_update(context, data_dict)

    # Send notification if needed
    if notify:
        dataset['url'] = toolkit.url_for('dataset_read', id=dataset.get('name'), qualified=True)
        curation = helpers.get_deposited_dataset_user_curation_status(dataset, user_obj.id)
        subj = mailer.compose_curation_email_subj(dataset)
        body = mailer.compose_curation_email_body(
            dataset, curation, user_obj.display_name, 'deposit')
        mailer.mail_user_by_id(user_obj.id, subj, body)

    return dataset


def package_publish_microdata(context, data_dict):
    default_error = 'Unknown microdata error'

    # Get data
    dataset_id = data_dict.get('id')
    nation = data_dict.get('nation')
    repoid = data_dict.get('repoid')

    # Check access
    toolkit.check_access('sysadmin', context)
    api_key = toolkit.config.get('ckanext.unhcr.microdata_api_key')
    if not api_key:
        raise toolkit.NotAuthorized('Microdata API Key is not set')

    # Get dataset/survey
    headers = {'X-Api-Key': api_key}
    dataset = toolkit.get_action('package_show')(context, {'id': dataset_id})
    survey = helpers.convert_dataset_to_microdata_survey(dataset, nation, repoid)
    idno = survey['study_desc']['title_statement']['idno']

    try:

        # Publish dataset
        url = 'https://microdata.unhcr.org/index.php/api/datasets/create/survey/%s' % idno
        response = requests.post(url, headers=headers, json=survey).json()
        if response.get('status') != 'success':
            raise RuntimeError(str(response.get('errors', default_error)))
        template = 'https://microdata.unhcr.org/index.php/catalog/%s'
        survey['url'] = template % response['dataset']['id']
        survey['resources'] = []
        survey['files'] = []

        # Pubish resources/files
        file_name_counter = {}
        if dataset.get('resources', []):
            url = 'https://microdata.unhcr.org/index.php/api/datasets/%s/%s'
            for resource in dataset.get('resources', []):

                # resource
                resouce_url = url % (idno, 'resources')
                md_resource = helpers.convert_resource_to_microdata_resource(resource)
                response = requests.post(
                    resouce_url, headers=headers, json=md_resource).json()
                if response.get('status') != 'success':
                    raise RuntimeError(str(response.get('errors', default_error)))
                survey['resources'].append(response['resource'])

                # file
                file_url = url % (idno, 'files')
                file_name = resource['url'].split('/')[-1]
                file_path = helpers.get_resource_file_path(resource)
                file_mime = resource['mimetype']
                if not file_name or not file_path:
                    continue
                file_name_counter.setdefault(file_name, 0)
                file_name_counter[file_name] += 1
                if file_name_counter[file_name] > 1:
                    file_name = helpers.add_file_name_suffix(
                        file_name, file_name_counter[file_name] - 1)
                with open(file_path, 'rb') as file_obj:
                    file = (file_name, file_obj, file_mime)
                    response = requests.post(
                        file_url, headers=headers, files={'file': file}).json()
                # TODO: update
                # it's a hack to overcome incorrect Microdata responses
                # unsupported file types fail this way and we are skipping them
                if not isinstance(response, dict):
                    continue
                if response.get('status') != 'success':
                    raise RuntimeError(str(response.get('errors', default_error)))
                survey['files'].append(response)

    except requests.exceptions.HTTPError as exception:
        log.exception(exception)
        raise RuntimeError('Microdata connection failed')

    return survey


def package_get_microdata_collections(context, data_dict):
    default_error = 'Unknown microdata error'

    # Check access
    toolkit.check_access('sysadmin', context)
    api_key = toolkit.config.get('ckanext.unhcr.microdata_api_key')
    if not api_key:
        raise toolkit.NotAuthorized('Microdata API Key is not set')

    try:

        # Get collections
        headers = {'X-Api-Key': api_key}
        url = 'https://microdata.unhcr.org/index.php/api/collections'
        response = requests.get(url, headers=headers).json()
        if response.get('status') != 'success':
            raise RuntimeError(str(response.get('errors', default_error)))
        collections = response['collections']

    except requests.exceptions.HTTPError as exception:
        log.exception(exception)
        raise RuntimeError('Microdata connection failed')

    return collections


@toolkit.chained_action
def package_collaborator_create(up_func, context, data_dict):

    m = context.get('model', model)
    user_id = toolkit.get_or_bust(data_dict, 'user_id')
    user = m.User.get(user_id)
    if not user:
        raise toolkit.ObjectNotFound("User not found")

    if user.external:
        message = 'Partner users can not be a dataset collaborator'
        raise toolkit.ValidationError({'message': message}, error_summary=message)

    return up_func(context, data_dict)


# Organization

def organization_create(context, data_dict):

    # When creating an organization, if the user is not a sysadmin it will be
    # created as pending, and sysadmins notified

    org_dict = create_core.organization_create(context, data_dict)

    # We create an organization as usual because we can't set
    # state=approval_needed on creation step and then
    # we patch the organization

    # Notify sysadmins
    notify_sysadmins = False
    user = get_core.user_show(context, {'id': context['user']})
    if not user['sysadmin']:
        # Not a sysadmin, create as pending and notify sysadmins (if all went
        # well)
        context['__unhcr_state_pending'] = True
        org_dict = patch_core.organization_patch(context,
            {'id': org_dict['id'], 'state': 'approval_needed'})
        notify_sysadmins = True
    if notify_sysadmins:
        try:
            for user in helpers.get_sysadmins():
                if user.email:
                    subj = mailer.compose_container_email_subj(org_dict, event='request')
                    body = mailer.compose_request_container_email_body(
                        org_dict,
                        user,
                        _get_user_obj(context),
                    )
                    mailer.mail_user(user, subj, body)
        except MailerException:
            message = '[email] Data container request notification is not sent: {0}'
            log.critical(message.format(org_dict['title']))

    return org_dict


def organization_member_create(context, data_dict):

    m = context.get('model', model)
    username = toolkit.get_or_bust(data_dict, 'username')
    user = m.User.get(username)
    if not user:
        raise toolkit.ObjectNotFound("User not found")

    if user.external:
        message = 'Partner users can not be an organisation member'
        raise toolkit.ValidationError({'message': message}, error_summary=message)

    if not data_dict.get('not_notify'):

        # Get container/user
        container = toolkit.get_action('organization_show')(context, {'id': data_dict['id']})
        user = toolkit.get_action('user_show')(context, {'id': data_dict['username']})

        # Notify the user
        subj = mailer.compose_membership_email_subj(container)
        body = mailer.compose_membership_email_body(container, user, 'create')
        mailer.mail_user_by_id(user['id'], subj, body)

    return create_core.organization_member_create(context, data_dict)


def organization_member_delete(context, data_dict):

    if not data_dict.get('not_notify'):

        # Get container/user
        container = toolkit.get_action('organization_show')(context, {'id': data_dict['id']})
        user = toolkit.get_action('user_show')(context, {'id': data_dict['user_id']})

        # Notify the user
        subj = mailer.compose_membership_email_subj(container)
        body = mailer.compose_membership_email_body(container, user, 'delete')
        mailer.mail_user_by_id(user['id'], subj, body)

    return delete_core.organization_member_delete(context, data_dict)


def organization_list_all_fields(context, data_dict):
    """
    Customized organization_list action.
    This action is many times more efficient than calling organization_list
    https://docs.ckan.org/en/2.8/api/index.html#ckan.logic.action.get.organization_list
    with {'all_fields': True, 'include_extras': True}
    but it only allows a much more constrained list of params.

    :param type: group type (optional, default: ``'data-container'``)
    :type type: string
    :param order_by: the field to sort the list by (optional, default: ``'title'``)
    :type order_by: string
    """
    toolkit.check_access('organization_list_all_fields', context, data_dict)
    m = context.get('model', model)
    session = context.get('session', m.Session)
    group_type = data_dict.get('type', 'data-container')
    order_by = data_dict.get('order_by', 'title')

    extra_cols = [rec[0] for rec in session.query(m.GroupExtra.key).distinct()]
    group_table = m.meta.metadata.tables['group']
    group_extra_table = m.meta.metadata.tables['group_extra']
    allowed_cols = [col.key for col in group_table.columns] + extra_cols
    if order_by not in allowed_cols:
        raise toolkit.Invalid("'order_by' must be one of {}".format(allowed_cols))

    join_obj = group_table
    select_cols = [col for col in group_table.columns]
    for col in extra_cols:
        extras_alias = aliased(group_extra_table, name='extras_{}'.format(col))
        select_cols.append(extras_alias.c.value.label(col))
        join_obj = join_obj.join(
            extras_alias,
            and_(
                group_table.c.id==extras_alias.c.group_id,
                extras_alias.c.key==col,
                extras_alias.c.state=='active',
            ), isouter=True,
        )

    sql = select(
        select_cols
    ).select_from(
        join_obj
    ).where(
        and_(
            group_table.c.type==group_type,
            group_table.c.state=='active',
            group_table.c.is_organization==True,
        )
    ).order_by(
        order_by
    )
    result = session.execute(sql).fetchall()

    organization_plugin = lib_plugins.lookup_group_plugin(group_type)
    schema = organization_plugin.form_to_db_schema()

    out_list = []
    for row in result:
        raw_dict = {k:v for k,v in row.items()}
        validated_dict, errors = organization_plugin.validate(
            context,
            raw_dict,
            schema,
            'organization_show'
        )
        if errors:
            raise toolkit.ValidationError(errors)
        validated_dict['display_name'] = validated_dict['title'] or validated_dict['name']
        out_list.append(validated_dict)

    return out_list


# Pending requests

def container_request_list(context, data_dict):
    all_fields = data_dict.get('all_fields', False)

    # Check permissions
    toolkit.check_access('sysadmin', context)

    # Containers
    containers = []
    query = (model.Session
        .query(model.Group.id)
        .filter(model.Group.state == 'approval_needed')
        .filter(model.Group.is_organization == True)
        .order_by(model.Group.name))
    for item in query.all():
        if all_fields:
            container = toolkit.get_action('organization_show')(context, {'id': item.id})
        else:
            container = item.id
        containers.append(container)

    return {
        'containers': containers,
        'count': len(containers),
    }


# Activity


def _package_admin_activity_list(full_list):
    return [
        a for a in full_list
        if 'curation_activity' in a.get('data', {})
        or a["activity_type"] == "download resource"
    ]

def _package_curation_activity_list(full_list):
    return [
        a for a in full_list
        if 'curation_activity' in a.get('data', {})
    ]

def _package_normal_activity_list(context, full_list):
    activities = [
        a for a in full_list
        if 'curation_activity' not in a.get('data', {})
        and a["activity_type"] != "download resource"
    ]
    # Filter out the activities that are related to `curation_state`
    activities = list(
        filter(
            lambda activity: get_core.activity_detail_list(
                context, {'id': activity['id']}).pop()
                .get('data', {})
                .get('package_extra', {})
                .get('key') not in ('curation_state', 'curator_id'),
            activities
        )
    )
    return activities


@toolkit.side_effect_free
@toolkit.chained_action
def package_activity_list(up_func, context, data_dict):
    toolkit.check_access('package_activity_list', context, data_dict)
    get_internal_activities = toolkit.asbool(
        data_dict.get('get_internal_activities'))
    package_id = toolkit.get_or_bust(data_dict, 'id')

    package = model.Package.get(package_id)
    user_is_container_admin = has_user_permission_for_group_or_org(
        package.owner_org,
        context['user'],
        'admin',
    ) if package else False

    full_list = up_func(context, data_dict)
    if get_internal_activities and user_is_container_admin:
        return _package_admin_activity_list(full_list)
    if get_internal_activities and not user_is_container_admin:
        return _package_curation_activity_list(full_list)
    return _package_normal_activity_list(context, full_list)


@toolkit.side_effect_free
def dashboard_activity_list(context, data_dict):
    full_list = get_core.dashboard_activity_list(context, data_dict)
    return [
        a for a in full_list
        if "curation_activity" not in a.get("data", {})
        and a["activity_type"] != "download resource"
    ]

@toolkit.side_effect_free
def user_activity_list(context, data_dict):
    full_list = get_core.user_activity_list(context, data_dict)
    return [
        a for a in full_list
        if "curation_activity" not in a.get("data", {})
        and a["activity_type"] != "download resource"
    ]


@toolkit.side_effect_free
def group_activity_list(context, data_dict):
    full_list = get_core.group_activity_list(context, data_dict)
    normal_activities = [
        a for a in full_list if 'curation_activity' not in a.get('data', {})]
    return normal_activities


@toolkit.side_effect_free
def organization_activity_list(context, data_dict):
    full_list = get_core.organization_activity_list(context, data_dict)
    normal_activities = [
        a for a in full_list if 'curation_activity' not in a.get('data', {})]
    return normal_activities


@toolkit.side_effect_free
def recently_changed_packages_activity_list(context, data_dict):
    full_list = get_core.recently_changed_packages_activity_list(context, data_dict)
    normal_activities = [
        a for a in full_list if 'curation_activity' not in a.get('data', {})]
    return normal_activities


# Without this action our `*_activity_list` is not overriden (ckan bug?)
def package_activity_list_html(context, data_dict):
    activity_stream = toolkit.get_action('package_activity_list')(context, data_dict)
    offset = int(data_dict.get('offset', 0))
    extra_vars = {
        'controller': 'package',
        'action': 'activity',
        'id': data_dict['id'],
        'offset': offset,
    }
    return activity_streams.activity_list_to_html(
        context, activity_stream, extra_vars)


@toolkit.side_effect_free
def dashboard_activity_list_html(context, data_dict):
    '''Override core ckan dashboard_activity_list_html action so download resource
    activities are not rendered in the HTML.
    '''
    activity_stream = toolkit.get_action('dashboard_activity_list')(
        context, data_dict)

    user_id = context['user']
    offset = int(data_dict.get('offset', 0))
    extra_vars = {
        'controller': 'user',
        'action': 'dashboard',
        'id': user_id,
        'offset': offset,
    }
    return activity_streams.activity_list_to_html(
        context, activity_stream, extra_vars
    )


@toolkit.side_effect_free
def user_activity_list_html(context, data_dict):
    '''Override core ckan user_activity_list_html action so download resource
    activities are not rendered in the HTML.
    '''
    activity_stream = toolkit.get_action('user_activity_list')(
        context, data_dict)

    offset = int(data_dict.get('offset', 0))
    extra_vars = {
        'controller': 'user',
        'action': 'activity',
        'id': data_dict['id'],
        'offset': offset,
    }
    return activity_streams.activity_list_to_html(
        context, activity_stream, extra_vars
    )


# Without this action the `*_activity_list` is not overriden (ckan bug?)
def group_activity_list_html(context, data_dict):
    activity_stream = group_activity_list(context, data_dict)
    offset = int(data_dict.get('offset', 0))
    extra_vars = {
        'controller': 'group',
        'action': 'activity',
        'id': data_dict['id'],
        'offset': offset,
    }
    return activity_streams.activity_list_to_html(
        context, activity_stream, extra_vars)


# Without this action the `*_activity_list` is not overriden (ckan bug?)
def organization_activity_list_html(context, data_dict):
    activity_stream = organization_activity_list(context, data_dict)
    offset = int(data_dict.get('offset', 0))
    extra_vars = {
        'controller': 'organization',
        'action': 'activity',
        'id': data_dict['id'],
        'offset': offset,
    }

    return activity_streams.activity_list_to_html(
        context, activity_stream, extra_vars)


# Without this action the `*_activity_list` is not overriden (ckan bug?)
def recently_changed_packages_activity_list_html(context, data_dict):
    activity_stream = recently_changed_packages_activity_list(
        context, data_dict)
    offset = int(data_dict.get('offset', 0))
    extra_vars = {
        'controller': 'package',
        'action': 'activity',
        'offset': offset,
    }
    return activity_streams.activity_list_to_html(
        context, activity_stream, extra_vars)


# Datastore

@toolkit.side_effect_free
def datasets_validation_report(context, data_dict):

    toolkit.check_access('datasets_validation_report', context, data_dict)
    search_params = {
        'q': '*:*',
        'include_private': True,
        'rows': 1000
    }
    query = toolkit.get_action('package_search')({'ignore_auth': True}, search_params)

    count = query['count']
    datasets = query['results']

    out = {
        'count': count,
        'datasets': [],
    }

    # get the schema
    package_plugin = lib_plugins.lookup_package_plugin('dataset')
    schema = package_plugin.update_package_schema()
    for dataset in datasets:
        data, errors = package_plugin.validate(context, dataset, schema, 'package_update')
        if errors:
            out['datasets'].append({
                'id': dataset['id'],
                'name': dataset['name'],
                'errors': errors,
            })

    return out


def _fail_task(context, task, error):
    task['error'] = json.dumps(error)
    task['state'] = 'error'
    task['last_updated'] = str(datetime.datetime.utcnow())
    return toolkit.get_action('task_status_update')(context, task)


def _task_is_stale(task):
    assume_task_stale_after = datetime.timedelta(seconds=3600)
    updated = datetime.datetime.strptime(task['last_updated'], '%Y-%m-%dT%H:%M:%S.%f')
    time_since_last_updated = datetime.datetime.utcnow() - updated
    return time_since_last_updated > assume_task_stale_after


def _should_resubmit(context, task, metadata):
    if task['state'] != 'complete':
        return False

    try:
        resource_show = toolkit.get_action('resource_show')
        resource_dict = resource_show(context, {'id': task['entity_id']})
    except toolkit.ObjectNotFound:
        return False

    if resource_dict.get('last_modified') and metadata.get('task_created'):
        try:
            last_modified_datetime = parse_date(resource_dict['last_modified'])
            task_created_datetime = parse_date(metadata['task_created'])
            if last_modified_datetime > task_created_datetime:
                log.debug('Uploaded file more recent: {0} > {1}'.format(
                        last_modified_datetime,
                        task_created_datetime,
                    )
                )
                return True
        except ValueError:
            pass
    elif (
        resource_dict.get('url')
        and metadata.get('original_url')
        and resource_dict['url'] != metadata['original_url']
    ):
        log.debug('URLs are different: {0} != {1}'.format(
                resource_dict['url'],
                metadata['original_url'],
            )
        )
        return True

    return False


def scan_submit(context, data_dict):
    resource_id = toolkit.get_or_bust(data_dict, "id")
    toolkit.check_access('scan_submit', context, data_dict)

    clamav_service_base_url = toolkit.config.get('ckanext.unhcr.clamav_url')
    site_url = toolkit.config.get('ckan.site_url')
    callback_url = toolkit.url_for('/api/3/action/scan_hook', qualified=True)
    site_user = toolkit.get_action('get_site_user')({'ignore_auth': True}, {})

    try:
        resource_dict = toolkit.get_action('resource_show')(context, {'id': resource_id})
    except toolkit.ObjectNotFound:
        return False

    task = {
        'entity_id': resource_id,
        'entity_type': 'resource',
        'task_type': 'clamav',
        'last_updated': str(datetime.datetime.utcnow()),
        'state': 'submitting',
        'key': 'clamav',
        'value': '{}',
        'error': 'null',
    }

    payload = json.dumps({
        'api_key': site_user['apikey'],
        'job_type': 'scan',
        'result_url': callback_url,
        'metadata': {
            'ckan_url': site_url,
            'resource_id': resource_id,
            'task_created': task['last_updated'],
            'original_url': resource_dict.get('url'),
        }
    })

    try:
        existing_task = toolkit.get_action('task_status_show')(context, {
            'entity_id': resource_id,
            'task_type': 'clamav',
            'key': 'clamav'
        })
        if (
            existing_task.get('state') == 'pending'
            and not _task_is_stale(existing_task)
        ):
            log.info(
                'A pending task was found {} for this resource, so '
                'skipping this duplicate task'.format(existing_task['id'])
            )
            return False
    except toolkit.ObjectNotFound:
        pass

    context['ignore_auth'] = True
    toolkit.get_action('task_status_update')(context, task)

    if not clamav_service_base_url:
        error = {'message': 'Could not submit to Clam AV Service.'}
        _fail_task(context, task, error)
        return False

    try:
        r = requests.post(
            urljoin(clamav_service_base_url, 'job'),
            headers={'Content-Type': 'application/json'},
            data=payload,
        )
        r.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        error = {'message': 'Could not connect to Clam AV Service.', 'details': str(e)}
        _fail_task(context, task, error)
        raise toolkit.ValidationError(error)
    except requests.exceptions.HTTPError as e:
        m = 'An Error occurred while sending the job: {0}'.format(e.message)
        try:
            body = e.response.json()
        except ValueError:
            body = e.response.text
        error = {'message': m, 'details': body, 'status_code': r.status_code}
        _fail_task(context, task, error)
        raise toolkit.ValidationError(error)

    task['value'] = r.text
    task['state'] = 'pending'
    task['last_updated'] = str(datetime.datetime.utcnow()),
    toolkit.get_action('task_status_update')(context, task)

    return True


def scan_hook(context, data_dict):
    metadata, status = toolkit.get_or_bust(data_dict, ['metadata', 'status'])
    resource_id = toolkit.get_or_bust(metadata, 'resource_id')

    toolkit.check_access('scan_hook', context, {'id': resource_id})

    task = toolkit.get_action('task_status_show')(context, {
        'entity_id': resource_id,
        'task_type': 'clamav',
        'key': 'clamav'
    })

    task['state'] = status
    task['last_updated'] = str(datetime.datetime.utcnow())
    task['value'] = json.dumps(data_dict)
    task['error'] = json.dumps(data_dict.get('error'))

    task = toolkit.get_action('task_status_update')({'ignore_auth': True}, task)

    if task['state'] == 'error':
        recipients = toolkit.aslist(toolkit.config.get('ckanext.unhcr.error_emails', []))
        for address in recipients:
            subj = '[UNHCR RIDL] Error performing Clam AV Scan'
            core_mailer.mail_recipient(
                'admin',
                address,
                subj,
                json.dumps(data_dict, indent=4)
            )
    elif task['state'] == 'complete' and task['value'] and data_dict.get('data'):
        scan_status = data_dict.get('data').get('status_code')
        if scan_status == 1:
            # file is infected
            resource = toolkit.get_action('resource_show')(context, {'id': resource_id})
            resource_name = resource['name'] or "Unnamed resource"
            recipients = mailer.get_infected_file_email_recipients()
            scan_report = data_dict.get('data').get('description', '')
            for recipient in recipients:
                subj = mailer.compose_infected_file_email_subj()
                body = mailer.compose_infected_file_email_body(
                    recipient,
                    resource_name,
                    resource['package_id'],
                    resource['id'],
                    scan_report
                )
                mailer.mail_user_by_id(recipient['id'], subj, body)

    if _should_resubmit(context, task, metadata):
        log.debug(
            'Resource {} has been modified, resubmitting to Clam AV'.format(resource_id)
        )
        toolkit.get_action('scan_submit')(context, {'id': resource_id})

    return data_dict


@toolkit.chained_action
def resource_create(up_func, context, data_dict):
    toolkit.check_access('resource_create', context, data_dict)
    has_upload = data_dict.get('upload') is not None
    resource = up_func(context, data_dict)
    if has_upload:
        toolkit.get_action('scan_submit')(context, {'id': resource['id']})
    return resource


@toolkit.chained_action
def resource_update(up_func, context, data_dict):
    toolkit.check_access('resource_update', context, data_dict)
    has_upload = data_dict.get('upload') is not None
    resource = up_func(context, data_dict)
    if has_upload:
        toolkit.get_action('scan_submit')(context, {'id': resource['id']})
    return resource


# Access Requests

def extract_keys_by_prefix(dct, prefix):
    return {
        k.replace(prefix, '', 1): v for k, v in dct.items() if k.startswith(prefix)
    }

def dictize_access_request(req):
    package = extract_keys_by_prefix(req, 'package_')
    group = extract_keys_by_prefix(req, 'group_')
    user = extract_keys_by_prefix(req, 'user_')
    access_request = extract_keys_by_prefix(req, 'access_requests_')
    access_request['user'] = user
    access_request['object'] = group if group['id'] else package
    return access_request


@toolkit.side_effect_free
def access_request_list_for_user(context, data_dict):
    """
    Return a list of all access requests the user can see

    :param status: ``'requested'``, ``'approved'`` or ``'rejected'``
      (default: ``'requested'``)
    :type status: string

    :returns: A list of AccessRequest objects
    :rtype: list of dictionaries
    """
    m = context.get('model', model)
    user_id = toolkit.get_or_bust(context, "user")
    status = data_dict.get("status", "requested")
    if status not in ['requested', 'approved', 'rejected']:
        raise toolkit.ValidationError('Invalid status {}'.format(status))

    user = m.User.get(user_id)
    if not user:
        raise toolkit.ObjectNotFound("User not found")

    toolkit.check_access('access_request_list_for_user', context, data_dict)

    access_requests_table = m.meta.metadata.tables["access_requests"]
    group_table = m.meta.metadata.tables["group"]
    package_table = m.meta.metadata.tables["package"]
    user_table = m.meta.metadata.tables["user"]

    select_cols = (
        [c for c in access_requests_table.columns] +
        [c for c in group_table.columns] +
        [c for c in package_table.columns] +
        [
            c for c in user_table.columns
            if c.name != 'plugin_extras'
            and c.name != 'password'
            and c.name != 'apikey'
        ]
    )

    sql = select(
        select_cols, use_labels=True,
    ).select_from(
        access_requests_table.join(
            package_table,
            and_(
                access_requests_table.c.object_type == "package",
                access_requests_table.c.object_id == package_table.c.id,
            ), isouter=True,
        ).join(
            group_table,
            and_(
                access_requests_table.c.object_type == "organization",
                access_requests_table.c.object_id == group_table.c.id,
            ), isouter=True,
        ).join(
            user_table,
            access_requests_table.c.user_id == user_table.c.id
        )
    ).order_by(
        desc(access_requests_table.c.timestamp)
    ).where(
        access_requests_table.c.status == status
    )

    if user.sysadmin:
        return [dictize_access_request(req) for req in m.Session.execute(sql).fetchall()]

    organizations = toolkit.get_action("organization_list_for_user")(
        context, {"id": user_id, "permission": "admin"}
    )
    containers = [o["id"] for o in organizations]
    if not containers:
        return []

    sql = sql.where(
        or_(
            and_(
                access_requests_table.c.object_type == "package",
                package_table.c.owner_org.in_(containers),
            ),
            and_(
                access_requests_table.c.object_type == "organization",
                access_requests_table.c.object_id.in_(containers),
            ),
            and_(
                access_requests_table.c.object_type == "user",
                access_requests_table.c.data["default_containers"].has_any(array(containers)),
            )
        )
    )

    return [dictize_access_request(req) for req in m.Session.execute(sql).fetchall()]


def _validate_status(status):
    valid = ['approved', 'rejected']
    if status not in valid:
        raise toolkit.ValidationError("'status' must be one of {}".format(str(valid)))

def _validate_role(role):
    valid = ['member', 'editor', 'admin']
    if role not in valid:
        raise toolkit.ValidationError("'role' must be one of {}".format(str(valid)))

def _validate_object_type(object_type):
    valid = ['organization', 'package', 'user']
    if object_type not in valid:
        raise toolkit.ValidationError("'object_type' must be one of {}".format(str(valid)))

def _validate_data(data):
    try:
        json.dumps(data)
    except TypeError:
        raise toolkit.ValidationError("'data' must be JSON-serializable")

def access_request_update(context, data_dict):
    """
    Approve or reject a request for access to a container or dataset

    :param id: access request id
    :type id: string
    :param status: new status value ('approved', 'rejected')
    :type status: string
    """
    m = context.get('model', model)
    request_id = toolkit.get_or_bust(data_dict, "id")
    status = toolkit.get_or_bust(data_dict, "status")
    _validate_status(status)
    request = model.Session.query(AccessRequest).get(request_id)
    if not request:
        raise toolkit.ObjectNotFound("Access Request not found")

    toolkit.check_access('access_request_update', context, data_dict)

    if request.object_type == 'package':
        _data_dict = {
            'id': request.object_id,
            'user_id': request.user_id,
            'capacity': request.role,
            'send_mail': True,
        }
        if status == 'approved':
            toolkit.get_action('package_collaborator_create')(
                context, _data_dict
            )
    elif request.object_type == 'organization':
        _data_dict = {
            'id': request.object_id,
            'username': request.user_id,
            'role': request.role,
        }
        if status == 'approved':
            toolkit.get_action('organization_member_create')(
                context, _data_dict
            )
    elif request.object_type == 'user':
        state = {'approved':  m.State.ACTIVE, 'rejected': m.State.DELETED}[status]
        _data_dict = {'id': request.object_id, 'state': state}
        user = toolkit.get_action('external_user_update_state')(
            context, _data_dict
        )

        if status == 'approved':
            # Notify the user
            subj = mailer.compose_account_approved_email_subj()
            body = mailer.compose_account_approved_email_body(user)
            mailer.mail_user_by_id(user['id'], subj, body)
    else:
        raise toolkit.Invalid("Unknown Object Type")

    request.status = status
    request.actioned_by = model.User.by_name(context['user']).id
    model.Session.commit()
    model.Session.refresh(request)

    return {
        col.name: getattr(request, col.name)
        for col in request.__table__.columns
    }


def access_request_create(context, data_dict):
    """
    Request access to a container or dataset

    :param object_id: uuid of the container or dataset we are requesting access to
    :type object_id: string
    :param object_type: type of object we are requesting access to
        ('organization', 'package', 'user')
    :type object_type: string
    :param message: user's message to the admin who will review the request
    :type message: string
    :param role: requested level of access ('member', 'editor', 'admin')
    :type role: string
    :param data: Optional dict containing any extra info to store about the request
        The dict must be JSON-serializable
    :type data: dict
    """
    m = context.get('model', model)
    user_id = toolkit.get_or_bust(context, "user")
    user = m.User.get(user_id)
    if not user:
        raise toolkit.ObjectNotFound("User not found")

    object_id, object_type, message, role = toolkit.get_or_bust(
        data_dict,
        ['object_id', 'object_type', 'message', 'role'],
    )
    data = data_dict.get('data', {})

    if not message:
        raise toolkit.ValidationError({'message': ["'message' is required"]})
    _validate_role(role)
    _validate_object_type(object_type)
    _validate_data(data)

    toolkit.check_access('access_request_create', context, data_dict)

    existing_request = model.Session.query(AccessRequest).filter(
        AccessRequest.user_id==user.id,
        AccessRequest.object_id==object_id,
        AccessRequest.status=='requested'
    ).all()
    if existing_request:
        raise toolkit.ValidationError(
            "You've already submitted a request to access this {}.".format(object_type)
        )

    request = AccessRequest(
        user_id=user.id,
        object_id=object_id,
        object_type=object_type,
        message=message,
        role=role,
        data=data,
    )
    model.Session.add(request)
    if not context.get('defer_commit'):
        model.Session.commit()
        model.Session.refresh(request)
    else:
        model.Session.flush()

    return {
        col.name: getattr(request, col.name)
        for col in request.__table__.columns
    }


def external_user_update_state(context, data_dict):
    """
    Change the status of an external user
    Any internal user with container admin privileges or higher
    can change the status of another user when:
    - The target user is external
    - The target user's current status is 'pending'
    Additionally, a sysadmin may change the status of another user at any time.

    :param id: The id or name of the target user
    :type id: string
    :param state: The new value of User.state
    :type state: string
    """
    m = context.get('model', model)
    user_id, state = toolkit.get_or_bust(data_dict, ['id', 'state'])

    toolkit.check_access('external_user_update_state', context, data_dict)

    if state not in m.State.all:
        raise toolkit.ValidationError('Invalid state {}'.format(state))

    user_obj = m.User.get(user_id)
    if not user_obj:
        raise toolkit.ObjectNotFound("User not found")
    user_obj.state = state
    m.Session.commit()
    m.Session.refresh(user_obj)

    return model_dictize.user_dictize(user_obj, context)


# Admin

def user_update_sysadmin(context, data_dict):
    """
    Add or remove a sysadmin user
    An authenticated sysadmin can promote an existing user to sysadmin
    or remove sysadmins priveledges from a user who already has them

    :param id: The id or name of the user
    :type id: string
    :param is_sysadmin: The new value of User.sysadmin
    :type is_sysadmin: bool
    """
    m = context.get('model', model)
    user_id, is_sysadmin = toolkit.get_or_bust(data_dict, ['id', 'is_sysadmin'])
    is_sysadmin = toolkit.asbool(is_sysadmin)

    toolkit.check_access('user_update_sysadmin', context, data_dict)

    user_obj = m.User.get(user_id)
    if not user_obj:
        raise toolkit.ObjectNotFound("User not found")
    user_obj.sysadmin = is_sysadmin
    m.Session.commit()
    m.Session.refresh(user_obj)

    return model_dictize.user_dictize(user_obj, context)


def search_index_rebuild(context, data_dict):
    toolkit.check_access('search_index_rebuild', context, data_dict)

    package_ids = [
        r[0]
        for r in model.Session.query(model.Package.id)
        .filter(model.Package.state != "deleted")
        .all()
    ]
    package_index = index_for(model.Package)
    errors = []
    context = {'model': model, 'ignore_auth': True, 'validate': False, 'use_cache': False}
    for pkg_id in package_ids:
        try:
            package_index.update_dict(
                core_logic.get_action('package_show')(context, {'id': pkg_id}),
                defer_commit=True
            )
        except Exception as e:
            errors.append('Encountered {error} processing {pkg}'.format(
                error=repr(e),
                pkg=pkg_id
            ))

    commit()
    return errors


# Autocomplete

@core_logic.schema.validator_args
def unhcr_autocomplete_schema(
        not_missing,
        unicode_safe,
        ignore_missing,
        natural_number_validator,
        boolean_validator
    ):
    return {
        'q': [not_missing, unicode_safe],
        'ignore_self': [ignore_missing],
        'limit': [ignore_missing, natural_number_validator],
        'include_external': [ignore_missing, boolean_validator],
    }


@core_logic.validate(unhcr_autocomplete_schema)
def user_autocomplete(context, data_dict):
    '''Return a list of user names that contain a string.

    :param q: the string to search for
    :type q: string
    :param limit: the maximum number of user names to return (optional,
        default: ``20``)
    :type limit: int
    :param include_external: include external users in the output (optional,
        default: ``False``)
    :type include_external: bool

    :rtype: a list of user dictionaries each with keys ``'name'``,
        ``'fullname'``, and ``'id'``
    '''
    m = context.get('model', model)
    user = toolkit.get_or_bust(context, "user")
    include_external_users = data_dict.get('include_external', False)

    toolkit.check_access('user_autocomplete', context, data_dict)

    q = data_dict['q']
    limit = data_dict.get('limit', 20)

    query = model.User.search(q)
    query = query.filter(model.User.state != model.State.DELETED)
    if not include_external_users:
        conditions = [
            model.User.email.ilike('%@{}'.format(domain))
            for domain in utils.get_internal_domains()
        ]
        query = query.filter(or_(*conditions))
    query = query.limit(limit)

    user_list = []
    for user in query.all():
        result_dict = {}
        for k in ['id', 'name', 'fullname']:
            result_dict[k] = getattr(user, k)

        user_list.append(result_dict)

    return user_list


@toolkit.chained_action
def user_list(up_func, context, data_dict):
    users = up_func(context, data_dict)
    m = context.get('model', model)

    if type(users[0]) == dict:
        users_db = (
            m.Session.query(m.User)
            .filter(m.User.id.in_([u['id'] for u in users]))
            .all()
        )
        id_to_external = {u.id: u.external for u in users_db}
        for user in users:
            user['external'] = id_to_external[user['id']]

    return users


@toolkit.chained_action
def user_show(up_func, context, data_dict):
    user = up_func(context, data_dict)
    user_obj = _get_user_obj(context)
    user['external'] = user_obj.external

    extras = _init_plugin_extras(user_obj.plugin_extras)
    extras = _validate_plugin_extras(extras['unhcr'])

    user['focal_point'] = extras['focal_point']
    user['expiry_date'] = extras['expiry_date']
    user['default_containers'] = extras['default_containers']

    return user


@toolkit.chained_action
def user_create(up_func, context, data_dict):

    m = context.get('model', model)
    if len(m.Session.query(m.User).filter(m.User.email==data_dict['email']).all()) > 0:
        raise toolkit.ValidationError({
            'email': [
                "The email address '{}' already belongs to a registered user.".format(
                    data_dict['email']
                )
            ]
        })

    user = up_func(context, data_dict)
    user_obj = _get_user_obj(context)

    if not user_obj.external:
        return user

    if not data_dict.get('focal_point'):
        raise toolkit.ValidationError({'focal_point': ["A focal point must be specified"]})

    if not isinstance(data_dict.get('default_containers'), list):
        raise toolkit.ValidationError({'default_containers': ["Specify one or more containers"]})

    plugin_extras = _init_plugin_extras(user_obj.plugin_extras)
    expiry_date = datetime.date.today() + datetime.timedelta(
        days=toolkit.config.get(
            'ckanext.unhcr.external_accounts_expiry_delta',
            180  # six months-ish
        )
    )
    plugin_extras['unhcr']['expiry_date'] = expiry_date.isoformat()
    plugin_extras['unhcr']['focal_point'] = data_dict['focal_point']
    plugin_extras['unhcr']['default_containers'] = data_dict['default_containers']
    user_obj.plugin_extras = plugin_extras

    if not context.get('defer_commit'):
        m = context.get('model', model)
        model.Session.commit()

    user['expiry_date'] = plugin_extras['unhcr']['expiry_date']
    user['focal_point'] = plugin_extras['unhcr']['focal_point']
    user['default_containers'] = plugin_extras['unhcr']['default_containers']
    return user


def _init_plugin_extras(plugin_extras):
    out_dict = copy.deepcopy(plugin_extras)
    if not out_dict:
        out_dict = {}
    if 'unhcr' not in out_dict:
        out_dict['unhcr'] = {}
    return out_dict


def _validate_plugin_extras(extras):
    CUSTOM_FIELDS = [
        {'name': 'focal_point', 'default': ''},
        {'name': 'expiry_date', 'default': None},
        {'name': 'default_containers',  'default': []},
    ]
    if not extras:
        extras = {}
    out_dict = {}
    for field in CUSTOM_FIELDS:
        out_dict[field['name']] = extras.get(field['name'], field['default'])
    return out_dict
