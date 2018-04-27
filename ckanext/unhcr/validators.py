import logging
from ckan.plugins.toolkit import Invalid
from ckanext.unhcr.helpers import get_linked_datasets_for_form
log = logging.getLogger(__name__)


# Module API

def linked_datasets(value, context):

    # Check if the user has access to the linked datasets
    selected = value if isinstance(value, list) else value.strip('{}').split(',')
    allowed = _get_allowed_linked_datasets()
    for id in selected:
        if id not in allowed:
            raise Invalid('Invalid linked datasets')

    return value


# Internal

# TODO:
# it could be better to extract core linked datasets
# preparing function to use here and in the helpers
def _get_allowed_linked_datasets():
    datasets = []
    for container in get_linked_datasets_for_form():
        for dataset in container['children']:
            datasets.append(dataset['value'])
    return datasets