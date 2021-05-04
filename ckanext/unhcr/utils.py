import json
from functools import wraps
import ckan.plugins.toolkit as toolkit
# TODO: move here helpers not used in templates?


INTERNAL_DOMAINS = ['unhcr.org']

def get_internal_domains():
    return toolkit.aslist(
        toolkit.config.get('ckanext.unhcr.internal_domains', INTERNAL_DOMAINS),
        sep = ','
    )


def normalize_list(value):
    if isinstance(value, list):
        return value
    value = value.strip('{}')
    if value:
        return value.split(',')
    return []


def get_module_functions(module_path):
    module_functions = {}
    module = __import__(module_path)

    for part in module_path.split('.')[1:]:
        module = getattr(module, part)

    for key, value in module.__dict__.items():
        if not key.startswith('_') and (
            hasattr(value, '__call__')
                and (value.__module__ == module_path)):
            module_functions[key] = value
    return module_functions


def user_is_external(user):
    '''
    Returns True if user email is not in the managed internal domains.
    '''
    if user.sysadmin:
        return False

    try:
        domain = user.email.split('@')[1]
    except AttributeError:
        return True

    return domain not in get_internal_domains()


def resource_is_blocked(context, resource_id):
    try:
        task = toolkit.get_action('task_status_show')(context, {
            'entity_id': resource_id,
            'task_type': 'clamav',
            'key': 'clamav'
        })
        if task['state'] == 'complete' and task['value']:
            task_data = json.loads(task['value'])
            if task_data.get('data'):
                scan_status = task_data.get('data').get('status_code', '')
                if scan_status == 1:
                    return True
    except toolkit.ObjectNotFound:
        pass

    return False


def require_user(func):
    '''
    Decorator for flask view functions. Returns 403 response if no user is logged in
    '''
    @wraps(func)
    def view_wrapper(*args, **kwargs):
        if (not hasattr(toolkit.c, "user") or not toolkit.c.user):
            return toolkit.abort(403, "Forbidden")
        return func(*args, **kwargs)
    return view_wrapper
