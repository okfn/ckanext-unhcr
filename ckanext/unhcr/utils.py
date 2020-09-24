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
