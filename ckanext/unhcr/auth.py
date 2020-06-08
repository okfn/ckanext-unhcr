import logging
from ckan import model
from ckan.plugins import toolkit
import ckan.logic.auth.create as auth_create_core
import ckan.logic.auth.update as auth_update_core
import ckanext.datastore.logic.auth as auth_datastore_core
from ckan.logic.auth import get as core_get, get_resource_object
from ckanext.unhcr import helpers
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

    core_auth_functions = {}
    skip_actions = [
        'help_show',  # Let's not overreact
        'site_read',  # Because of madness in the API controller
        'organiation_list_for_user',  # Because of #4097
        'get_site_user',
        'user_reset',  # saml2
        'user_create',  # saml2
        'user_delete',  # saml2
        'request_reset',  # saml2
    ]
    module_path = 'ckan.logic.auth.get'
    module = __import__(module_path)

    for part in module_path.split('.')[1:]:
        module = getattr(module, part)

    for key, value in module.__dict__.items():
        if not key.startswith('_') and (
            hasattr(value, '__call__')
                and (value.__module__ == module_path)):
            core_auth_functions[key] = value
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
    overriden_auth_functions['organization_create'] = organization_create
    overriden_auth_functions['package_create'] = package_create
    overriden_auth_functions['package_update'] = package_update
    overriden_auth_functions['package_activity_list'] = package_activity_list
    overriden_auth_functions['dataset_collaborator_create'] = dataset_collaborator_create

    return overriden_auth_functions


@toolkit.auth_allow_anonymous_access
def site_read(context, data_dict):
    if toolkit.request.path.startswith('/api'):
        # Let individual API actions deal with their auth
        return {'success': True}
    elif toolkit.request.path == '/service/login':
        # Allow local logins
        return {'success': True}
    if not context.get('user'):
        return {'success': False}
    return {'success': True}


# Organization

@toolkit.auth_allow_anonymous_access
def organization_list_for_user(context, data_dict):
    if not context.get('user'):
        return {'success': False}
    else:
        return core_get.organization_list_for_user(context, data_dict)


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


# Package

def package_create(context, data_dict):

    # Data deposit
    if not data_dict:
        # All users can deposit datasets
        if toolkit.request.path == '/deposited-dataset/new':
            return {'success': True}
    else:
        deposit = helpers.get_data_deposit()
        if deposit['id'] == data_dict.get('owner_org'):
            return {'success': True}

    # Data container
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
            dataset, toolkit.c.userobj.id)
        if 'edit' in curation['actions']:
            return {'success': True}
        return {'success': False, 'msg': 'Not authorized to edit deposited dataset'}

    # Regular dataset
    return next_auth(context, data_dict)


def package_activity_list(context, data_dict):
    if toolkit.asbool(data_dict.get('get_curation_activities')):
        # Check if the user can see the curation activity,
        # for now we check if the user can edit the dataset
        return auth_update_core.package_update(context, data_dict)
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
    is_depositor = (
        dataset.get('type') == 'deposited-dataset' and
        dataset.get('creator_user_id') == getattr(context.get('auth_user_obj'), 'id', None))
    if not user or is_depositor or not visibility or visibility != 'restricted':
        return {
            'success': toolkit.check_access('resource_show', context, data_dict)}

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


@toolkit.auth_allow_anonymous_access
def unhcr_datastore_info(context, data_dict):
    return auth_datastore_core.datastore_auth(context, data_dict, 'resource_download')


@toolkit.auth_allow_anonymous_access
def unhcr_datastore_search(context, data_dict):
    return auth_datastore_core.datastore_auth(context, data_dict, 'resource_download')


@toolkit.auth_allow_anonymous_access
def unhcr_datastore_search_sql(context, data_dict):
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
    return {'success': True}


def datasets_validation_report(context, data_dict):
    return {'success': False}


@toolkit.chained_auth_function
def dataset_collaborator_create(next_auth, context, data_dict):
    dataset = toolkit.get_action('package_show')(
        {'ignore_auth': True}, {'id': data_dict['id']})
    if dataset['type'] == 'deposited-dataset':
        return {'success': False, 'msg': "Can't add collaborators to a Data Deposit"}
    return next_auth(context, data_dict)
