# TODO: move here helpers not used in templates?

# Misc

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
