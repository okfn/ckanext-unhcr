import logging
from ckan import model
from urlparse import urljoin
from ckan.plugins import toolkit
from ckan.lib.mailer import MailerException
import ckan.logic.action.get as get_core
import ckan.logic.action.create as create_core
import ckan.logic.action.update as update_core
import ckan.logic.action.patch as patch_core
import ckan.lib.activity_streams as activity_streams
from ckanext.unhcr import helpers, mailer
log = logging.getLogger(__name__)


# Package

def package_create(context, data_dict):
    userobj = toolkit.c.userobj

    # Create dataset
    dataset = create_core.package_create(context, data_dict)

    # Send notification if it's deposited and it's not testing env
    if dataset.get('type') == 'deposited-dataset' and hasattr(userobj, 'id'):
        dataset['url'] = toolkit.url_for('dataset_read', id=dataset.get('name'), qualified=True)
        curation = helpers.get_deposited_dataset_user_curation_status(dataset, userobj.id)
        subj = mailer.compose_curation_email_subj(dataset)
        body = mailer.compose_curation_email_body(
            dataset, curation, userobj.display_name, 'deposit')
        mailer.mail_user_by_id(userobj.id, subj, body)

    return dataset


# Organization

def organization_create(context, data_dict):

    # When creating an organization, if the user is not a sysadmin it will be
    # created as pending, and sysadmins notified

    org_dict = create_core.organization_create(context, data_dict)

    # We create an organization as usual because we can't set
    # state=approval_needed on creation step and then
    # we patch the organization

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
            mailer.mail_data_container_request_to_sysadmins(context, org_dict)
        except MailerException:
            message = '[email] Data container request notification is not sent: {0}'
            log.critical(message.format(org_dict['title']))

    return org_dict


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
    normal_activities = [
        a for a in full_list if 'curation_activity' not in a.get('data', {})]
    return normal_activities


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


# Without this action the `*_activity_list` is not overriden (ckan bug?)
def dashboard_activity_list_html(context, data_dict):
    activity_stream = dashboard_activity_list(context, data_dict)
    model = context['model']
    user_id = context['user']
    offset = data_dict.get('offset', 0)
    extra_vars = {
        'controller': 'user',
        'action': 'dashboard',
        'offset': offset,
        'id': user_id
    }
    return activity_streams.activity_list_to_html(context, activity_stream,
                                                  extra_vars)


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

# We ended up with double auth checks for every action
# because auth_audit requires calling non-unhcr auth functions too

@toolkit.chained_action
def datastore_info(action, context, data_dict):
    toolkit.check_access('unhcr_datastore_info', context, data_dict)
    return action(context, data_dict)


@toolkit.chained_action
#  @toolkit.side_effect_free
def datastore_search(action, context, data_dict):
    toolkit.check_access('unhcr_datastore_search', context, data_dict)
    return action(context, data_dict)


@toolkit.chained_action
#  @toolkit.side_effect_free
def datastore_search_sql(action, context, data_dict):
    toolkit.check_access('unhcr_datastore_search_sql', context, data_dict)
    return action(context, data_dict)
