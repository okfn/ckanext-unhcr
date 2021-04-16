import logging
from ckan import model
from ckan.authz import has_user_permission_for_group_or_org
from ckan.plugins import toolkit
import ckan.logic.auth.create as auth_create_core
import ckan.logic.auth.update as auth_update_core
import ckanext.datastore.logic.auth as auth_datastore_core
from ckan.logic.auth import get as core_get, get_resource_object
from ckanext.unhcr import helpers
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.utils import get_module_functions
log = logging.getLogger(__name__)


# General

def restrict_access_to_get_auth_functions():
    '''
    By default, all GET actions in CKAN core allow anonymous access (non
    logged in users). This is done by applying an allow_anonymous_access
    to the function itself. Rather than reimplementing all auth functions
    in our extension just to apply the `toolkit.auth_disallow_anonymous_access`
    decorator and redirect to the core one, we automate this process by
    importing all GET auth functions automatically (and setting the flag to
    False).
    '''

    core_auth_functions = get_module_functions('ckan.logic.auth.get')
    skip_actions = [
        'help_show',  # Let's not overreact
        'site_read',  # Because of madness in the API controller
        'organization_list_for_user',  # Because of #4097
        'get_site_user',
        'user_reset',  # saml2
        'user_create',  # saml2
        'user_delete',  # saml2
        'request_reset',  # saml2
    ]

    overriden_auth_functions = {}
    for key, value in core_auth_functions.items():

        if key in skip_actions:
            continue
        auth_function = toolkit.auth_disallow_anonymous_access(value)
        overriden_auth_functions[key] = auth_function

    # Handle these separately
    overriden_auth_functions['site_read'] = site_read
    overriden_auth_functions['organization_list_for_user'] = \
        organization_list_for_user
    overriden_auth_functions['package_activity_list'] = package_activity_list

    return overriden_auth_functions


@toolkit.auth_allow_anonymous_access
def site_read(context, data_dict):
    if toolkit.request.path.startswith('/api'):
        # Let individual API actions deal with their auth
        return {'success': True}

    userobj = context.get('auth_user_obj')
    if not userobj:
        return {'success': False}

    # we've granted external users site_read for the home page, but we
    # want to deny site_read for all other pages that only need site_read
    if userobj.external and toolkit.request.path != '/':
        return {'success': False}

    return {'success': True}


# Organization

@toolkit.auth_allow_anonymous_access
def organization_list_for_user(context, data_dict):
    if not context.get('user'):
        return {'success': False}
    else:
        return core_get.organization_list_for_user(context, data_dict)


@toolkit.chained_auth_function
def organization_show(next_auth, context, data_dict):
    user = context.get('auth_user_obj')
    if not user:
        return next_auth(context, data_dict)
    if user.external:
        deposit = helpers.get_data_deposit()
        if data_dict.get('id') in [deposit['name'], deposit['id']]:
            return {'success': True}
        else:
            return {'success': False}
    return next_auth(context, data_dict)


def organization_list_all_fields(next_auth, context, data_dict):
    try:
        toolkit.check_access('organization_list', context, data_dict)
        return {'success': True}
    except toolkit.NotAuthorized:
        return {'success': False}


def organization_create(context, data_dict):
    user_orgs = toolkit.get_action('organization_list_for_user')(context, {})

    # Allow to see `Request data container` button if user is an admin for an org
    if not data_dict:
        for user_org in user_orgs:
            if user_org['capacity'] == 'admin':
                return {'success': True}

    # Base access check
    result = auth_create_core.organization_create(context, data_dict)
    if not result['success']:
        return result

    # Check parent organization access
    if data_dict:
        for user_org in user_orgs:

            # Looking for orgs only where user is admin
            if user_org['capacity'] != 'admin':
                continue

            # Looking for only approved orgs
            if user_org['state'] != 'active':
                continue

            # Allow if parent matches
            for group in data_dict.get('groups', []):
                if group['name'] == user_org['name']:
                    return {'success': True}

    return {'success': False, 'msg': 'Not allowed to create a data container'}


def group_list_authz(context, data_dict):
    return {'success': True}


# Package

def package_create(context, data_dict):
    # Data deposit
    if not data_dict:
        try:
            # All users can deposit datasets
            if (
                toolkit.request.path == '/deposited-dataset/new' or
                toolkit.request.path.startswith('/deposited-dataset/edit/')
            ):
                return {'success': True}
        except TypeError:
            return {
                'success': False,
                'msg': 'package_create requires either a web request or a data_dict'
            }
    else:
        deposit = helpers.get_data_deposit()
        if deposit['id'] == data_dict.get('owner_org'):
            return {'success': True}

    # Data container
    context['model'] = context.get('model') or model
    return auth_create_core.package_create(context, data_dict)


@toolkit.chained_auth_function
def package_update(next_auth, context, data_dict):

    # Get dataset
    dataset_id = None
    if data_dict:
        dataset_id = data_dict['id']
    if context.get('package'):
        dataset_id = context['package'].id
    dataset = toolkit.get_action('package_show')(context, {'id': dataset_id})

    # Deposited dataset
    if dataset['type'] == 'deposited-dataset':
        curation = helpers.get_deposited_dataset_user_curation_status(
            dataset, getattr(context.get('auth_user_obj'), 'id', None))
        if 'edit' in curation['actions']:
            return {'success': True}
        return {'success': False, 'msg': 'Not authorized to edit deposited dataset'}

    # Regular dataset
    return next_auth(context, data_dict)


def package_activity_list(context, data_dict):
    if toolkit.asbool(data_dict.get('get_internal_activities')):
        # Check if the user can see the internal activity,
        # for now we check if the user can edit the dataset
        try:
            toolkit.check_access('package_update', context, data_dict)
            return {'success': True}
        except toolkit.NotAuthorized:
            return {'success': False}
    return {'success': True}


# Resource

def resource_download(context, data_dict):
    '''
    This is a new auth function that specifically controls access to the download
    of a resource file, as opposed to seeing the metadata of a resource (handled
    by `resource_show`

    If the parent dataset is marked as public or private in the custom visibility
    field, the authorization check is deferred to `resource_show` as the standard
    logic applies (we assume that the necessary validators are applied to keep
    `visibility` and `private` fields in sync).

    If the parent dataset is marked as `restricted` then  only users belonging to
    the dataset organization can download the file.
    '''

    # Prepare all the parts
    context['model'] = context.get('model') or model
    user = context.get('user')
    resource = get_resource_object(context, data_dict)
    dataset = toolkit.get_action('package_show')(
        {'ignore_auth': True}, {'id': resource.package_id})
    visibility = dataset.get('visibility')

    # Use default check
    user_id = getattr(context.get('auth_user_obj'), 'id', None)
    is_deposit = dataset.get('type') == 'deposited-dataset'
    if is_deposit:
        is_depositor = dataset.get('creator_user_id') == user_id
        curators = [u['id'] for u in helpers.get_data_curation_users(dataset)]
        is_curator = user_id in curators
    else:
        is_depositor = False
        is_curator = False

    if not user or is_depositor or is_curator or not visibility or visibility != 'restricted':
        try:
            toolkit.check_access('resource_show', context, data_dict)
            return {'success': True}
        except toolkit.NotAuthorized:
            return {'success': False}

    # Restricted visibility (public metadata but private downloads)
    if dataset.get('owner_org'):
        user_orgs = toolkit.get_action('organization_list_for_user')(
            {'ignore_auth': True}, {'id': user})
        user_in_owner_org = any(
            org['id'] == dataset['owner_org'] for org in user_orgs)
        if user_in_owner_org:
            return {'success': True}

    # Support for ckanext-collaborators style auth
    action = toolkit.get_action('dataset_collaborator_list_for_user')
    if user and action:
        datasets = action(context, {'id': user})
        return {
            'success': resource.package_id in [
                d['dataset_id'] for d in datasets
            ]
        }

    return {'success': False}


@toolkit.chained_auth_function
def datastore_info(next_auth, context, data_dict):
    parent_auth = auth_datastore_core.datastore_auth(
        context,
        data_dict,
        'resource_download'
    )
    if not parent_auth['success']:
        return parent_auth
    return next_auth(context, data_dict)


@toolkit.chained_auth_function
def datastore_search(next_auth, context, data_dict):
    parent_auth = auth_datastore_core.datastore_auth(
        context,
        data_dict,
        'resource_download'
    )
    if not parent_auth['success']:
        return parent_auth
    return next_auth(context, data_dict)


@toolkit.chained_auth_function
def datastore_search_sql(next_auth, context, data_dict):
    '''need access to view all tables in query'''

    for name in context['table_names']:
        name_auth = auth_datastore_core.datastore_auth(
            dict(context),  # required because check_access mutates context
            {'id': name},
            'resource_download')
        if not name_auth['success']:
            return {
                'success': False,
                'msg': 'Not authorized to read resource.'}
    return next_auth(context, data_dict)


def datasets_validation_report(context, data_dict):
    return {'success': False}


def scan_submit(context, data_dict):
    try:
        toolkit.check_access('resource_update', context, data_dict)
        return {'success': True}
    except toolkit.NotAuthorized:
        return {'success': False}


def scan_hook(context, data_dict):
    try:
        toolkit.check_access('resource_update', context, data_dict)
        return {'success': True}
    except toolkit.NotAuthorized:
        return {'success': False}


@toolkit.chained_auth_function
def dataset_collaborator_create(next_auth, context, data_dict):
    dataset = toolkit.get_action('package_show')(
        {'ignore_auth': True}, {'id': data_dict['id']})
    if dataset['type'] == 'deposited-dataset':
        return {'success': False, 'msg': "Can't add collaborators to a Data Deposit"}
    return next_auth(context, data_dict)


# Access Requests

def access_request_list_for_user(context, data_dict):
    user = context.get('user')
    orgs = toolkit.get_action("organization_list_for_user")(
        {"user": user},
        {"id": user, "permission": "admin"}
    )
    if len(orgs) > 0:
        return {'success': True}

    return {'success': False}

def access_request_update(context, data_dict):
    user = context.get('user')
    request_id = toolkit.get_or_bust(data_dict, "id")
    request = model.Session.query(AccessRequest).get(request_id)
    if not request:
        raise toolkit.ObjectNotFound("Access Request not found")

    if request.object_type == 'package':
        package = toolkit.get_action('package_show')(
            context, {'id': request.object_id}
        )
        org_id = package['owner_org']
        return {
            'success': has_user_permission_for_group_or_org(
                org_id, user, 'admin'
            )
        }
    elif request.object_type == 'organization':
        org_id = request.object_id
        return {
            'success': has_user_permission_for_group_or_org(
                org_id, user, 'admin'
            )
        }
    elif request.object_type == 'user':
        return external_user_update_state(context, {'id': request.object_id})

    raise toolkit.Invalid("Unknown Object Type")


def access_request_create(context, data_dict):
    return {'success': bool(context.get('user'))}


def external_user_update_state(context, data_dict):
    m = context.get('model', model)
    request_userobj = context.get('auth_user_obj')
    if not request_userobj:
        return {'success': False}

    target_user_id = toolkit.get_or_bust(data_dict, "id")
    target_userobj = m.User.get(target_user_id)
    if not target_userobj:
        raise toolkit.ObjectNotFound("User not found")

    # request_userobj is the user who is trying to perform the action
    # target_userobj is the user we're trying to modify

    if not target_userobj.external:
        return {'success': False, 'msg': "Can only perform this action on an external user"}
    if target_userobj.state != m.State.PENDING:
        return {'success': False, 'msg': "Can only change state of a 'pending' user"}

    access_requests = model.Session.query(AccessRequest).filter(
        AccessRequest.user_id==target_userobj.id,
        AccessRequest.object_id==target_userobj.id,
        AccessRequest.status=='requested',
        AccessRequest.object_type=='user',
    ).all()

    if not access_requests or len(access_requests) > 1:
        return {
            'success': False,
            'msg': "User must be associated with exactly one pending access request"
        }

    for container in access_requests[0].data['default_containers']:
        if has_user_permission_for_group_or_org(
            container, request_userobj.id, 'admin'
        ):
            return {'success': True}

    return {'success': False}


# Admin

def user_update_sysadmin(context, data_dict):
    return {'success': False}


def search_index_rebuild(context, data_dict):
    return {'success': False}


@toolkit.chained_auth_function
def user_show(next_auth, context, data_dict):
    auth_user_obj = context.get('auth_user_obj')
    if not auth_user_obj:
        return {'success': False}
    if auth_user_obj.external:
        if context['user'] == data_dict['id'] or auth_user_obj.id == data_dict['id']:
            return next_auth(context, data_dict)
        return {'success': False}
    return next_auth(context, data_dict)
