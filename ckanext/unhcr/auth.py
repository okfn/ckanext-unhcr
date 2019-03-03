import logging
from ckan.plugins import toolkit
import ckan.logic.auth.create as auth_create_core
import ckan.logic.auth.update as auth_update_core
from ckan.logic.auth import get as core_get
from ckanext.unhcr import helpers
log = logging.getLogger(__name__)


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

    return overriden_auth_functions


@toolkit.auth_allow_anonymous_access
def site_read(context, data_dict):
    if toolkit.request.path.startswith('/api'):
        # Let individual API actions deal with their auth
        return {'success': True}
    if not context.get('user'):
        return {'success': False}
    return {'success': True}


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


def package_create(context, data_dict):

    # For data deposit container
    if data_dict:
        depo = helpers.get_data_container_for_depositing()
        if depo['id'] == data_dict.get('owner_org'):
            return {'success': True}

    # For normal container
    return auth_create_core.package_create(context, data_dict)


def package_update(context, data_dict):

    # Get package id
    package_id = None
    if data_dict:
        package_id = data_dict['id']
    if context.get('package'):
        package_id = context['package'].id

    # For data deposit container
    if package_id:
        pack = toolkit.get_action('package_show')({}, {'id': package_id})
        depo = helpers.get_data_container_for_depositing()
        if (toolkit.c.userobj.id == pack.get('creator_user_id') and
            depo['id'] == pack.get('owner_org')):
                return {'success': True}

    # For normal container
    return auth_update_core.package_update(context, data_dict)
