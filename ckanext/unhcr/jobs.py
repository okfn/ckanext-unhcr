import logging
from ckan import model
from ckanext.unhcr import utils
import ckan.plugins.toolkit as toolkit
log = logging.getLogger(__name__)


# Module API

def process_dataset_fields(package_id):

    # Get package
    package_show = toolkit.get_action('package_show')
    package = package_show({'job': True}, {'id': package_id})

    # Modify package
    package = _modify_package(package)

    # Update package
    package_update = toolkit.get_action('package_update')
    package_update({'job': True}, package)


def process_dataset_links_on_create(package_id):
    context = {'model': model, 'job': True}

    # Create back references
    package = toolkit.get_action('package_show')(context, {'id': package_id})
    link_package_ids = utils.normalize_list(package.get('linked_datasets', []))
    _create_link_package_back_references(package_id, link_package_ids)


def process_dataset_links_on_delete(package_id):
    context = {'model': model, 'job': True}

    # Delete back references
    package = toolkit.get_action('package_show')(context, {'id': package_id})
    link_package_ids = utils.normalize_list(package.get('linked_datasets', []))
    _delete_link_package_back_references(package_id, link_package_ids)


def process_dataset_links_on_update(package_id):
    link_package_ids = _get_link_package_ids_from_revisions(package_id)

    # Create back references
    created_link_package_ids = set(link_package_ids['next']).difference(link_package_ids['prev'])
    _create_link_package_back_references(package_id, created_link_package_ids)

    # Delete back references
    removed_link_package_ids = set(link_package_ids['prev']).difference(link_package_ids['next'])
    _delete_link_package_back_references(package_id, removed_link_package_ids)


# Internal

def _modify_package(package):

    # data_range
    package = _modify_date_range(package, 'date_range_start', 'date_range_end')

    # process_status
    weights = {'raw' : 3, 'cleaned': 2, 'anonymized': 1}
    package = _modify_weighted_field(package, 'process_status', weights)

    # identifiability
    weights = {'personally_identifiable' : 2, 'anonymized': 1}
    package = _modify_weighted_field(package, 'identifiability', weights)

    # private
    if package['identifiability'] == 'personally_identifiable':
        package['private'] = True

    return package


def _modify_date_range(package, key_start, key_end):

    # Reset for generated
    package[key_start] = None
    package[key_end] = None

    # Iterate resources
    for resource in package['resources']:
        if resource.get(key_start, resource.get(key_end)) is None:
            continue
        # We could compare dates as strings because it's guarnateed to be YYYY-MM-DD
        package[key_start] = min(filter(None, [package[key_start], resource[key_start]]))
        package[key_end] = max(filter(None, [package[key_end], resource[key_end]]))

    return package


def _modify_weighted_field(package, key, weights):

    # Reset for generated
    package[key] = None

    # Iterate resources
    for resource in package['resources']:
        if resource.get(key) is None:
            continue
        package_weight = weights.get(package[key], 0)
        resource_weight = weights.get(resource[key], 0)
        if resource_weight > package_weight:
            package[key] = resource[key]

    return package


def _create_link_package_back_references(package_id, link_package_ids):
    context = {'model': model, 'job': True}

    # Create package back reference for every linked package
    for link_package_id in link_package_ids:
        link_package = toolkit.get_action('package_show')(context, {'id': link_package_id})
        back_package_ids = utils.normalize_list(link_package.get('linked_datasets', []))
        if package_id not in back_package_ids:
            link_package['linked_datasets'] = back_package_ids + [package_id]
            toolkit.get_action('package_update')(context, link_package)


def _delete_link_package_back_references(package_id, link_package_ids):
    context = {'model': model, 'job': True}

    # Delete package back reference for every unlinked package
    for link_package_id in link_package_ids:
        link_package = toolkit.get_action('package_show')(context, {'id': link_package_id})
        back_package_ids = utils.normalize_list(link_package.get('linked_datasets', []))
        if package_id in back_package_ids:
            back_package_ids.remove(package_id)
            link_package['linked_datasets'] = back_package_ids
            toolkit.get_action('package_update')(context, link_package)


def _get_link_package_ids_from_revisions(package_id):

    # Get revisions
    revisions = (model.Session.query(model.PackageExtraRevision)
        .filter(model.PackageExtraRevision.package_id == package_id,
                model.PackageExtraRevision.key == 'linked_datasets')
        .order_by(model.PackageExtraRevision.revision_timestamp)
        .all())

    # Prev revision
    prev = []
    if len(revisions) >= 2:
        revision = revisions[-2]
        if revision.state == 'active':
            prev = utils.normalize_list(revision.value)

    # Next revision
    next = []
    if len(revisions) >= 1:
        revision = revisions[-1]
        if revision.state == 'active':
            next = utils.normalize_list(revision.value)

    return {'prev': prev, 'next': next}
