import logging
import requests
from ckan import model
from ckan.plugins import toolkit
from ckan.lib.mailer import MailerException
import ckan.lib.plugins as lib_plugins
import ckan.logic.action.get as get_core
import ckan.logic.action.create as create_core
import ckan.logic.action.delete as delete_core
import ckan.logic.action.update as update_core
import ckan.logic.action.patch as patch_core
import ckan.lib.activity_streams as activity_streams
from ckanext.unhcr import helpers, mailer
from ckanext.scheming.helpers import scheming_get_dataset_schema

log = logging.getLogger(__name__)


# Package

def package_update(context, data_dict):
    userobj = toolkit.c.userobj

    # Decide if we need notification
    # - deposited-datset AND
    # - not a test env AND
    # - just published
    notify = False
    if data_dict.get('type') == 'deposited-dataset' and hasattr(userobj, 'id'):
        dataset = toolkit.get_action('package_show')(context, {'id': data_dict['id']})
        if dataset.get('state') == 'draft' and data_dict.get('state') == 'active':
            notify = True

    # Update dataset
    dataset = update_core.package_update(context, data_dict)

    # Send notification if needed
    if notify:
        dataset['url'] = toolkit.url_for('dataset_read', id=dataset.get('name'), qualified=True)
        curation = helpers.get_deposited_dataset_user_curation_status(dataset, userobj.id)
        subj = mailer.compose_curation_email_subj(dataset)
        body = mailer.compose_curation_email_body(
            dataset, curation, userobj.display_name, 'deposit')
        mailer.mail_user_by_id(userobj.id, subj, body)

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
                # usopported file types fail this way and we are skipping them
                if not isinstance(response, dict):
                    continue
                if response.get('status') != 'success':
                    raise RuntimeError(str(response.get('errors', default_error)))
                survey['files'].append(response)

    except requests.exceptions.HTTPError:
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

    except requests.exceptions.HTTPError:
        log.exception(exception)
        raise RuntimeError('Microdata connection failed')

    return collections


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
                        toolkit.c.userobj,
                    )
                    mailer.mail_user(user, subj, body)
        except MailerException:
            message = '[email] Data container request notification is not sent: {0}'
            log.critical(message.format(org_dict['title']))

    return org_dict


def organization_member_create(context, data_dict):

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


# Pending requests

def pending_requests_list(context, data_dict):
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

@toolkit.side_effect_free
def package_activity_list(context, data_dict):
    get_curation_activities = toolkit.asbool(
        data_dict.get('get_curation_activities'))
    full_list = get_core.package_activity_list(context, data_dict)
    full_list = [a for a in full_list if a["activity_type"] != "download resource"]
    curation_activities = [
        a for a in full_list if 'curation_activity' in a.get('data', {})]
    normal_activities = [
        a for a in full_list if 'curation_activity' not in a.get('data', {})]
    # Filter out the activities that are related `curation_state`
    normal_activities = list(filter(
        lambda activity: get_core.activity_detail_list(
            context, {'id': activity['id']}).pop()
            .get('data', {})
            .get('package_extra', {})
            .get('key') not in ('curation_state', 'curator_id'), normal_activities))
    return (curation_activities
        if get_curation_activities else normal_activities)


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
    activity_stream = package_activity_list(context, data_dict)
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
    context = {'model': model, 'session': model.Session, 'user': toolkit.c.user}
    for dataset in datasets:
        data, errors = package_plugin.validate(context, dataset, schema, 'package_update')
        if errors:
            out['datasets'].append({
                'id': dataset['id'],
                'name': dataset['name'],
                'errors': errors,
            })

    return out
