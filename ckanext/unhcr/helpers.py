import logging
from ckan import model
from ckan.logic import ValidationError
from ckan.plugins import toolkit
import ckan.lib.plugins as lib_plugins
from ckanext.unhcr import utils
log = logging.getLogger(__name__)


# General

def get_data_container(id, context=None):
    context = context or {'model': model}
    return toolkit.get_action('organization_show')(context, {'id': id})


def get_all_data_containers(exclude_ids=[]):
    data_containers = []
    context = {'model': model, 'ignore_auth': True}
    orgs = toolkit.get_action('organization_list')(context,
        {'type': 'data-container', 'all_fields': True})
    for org in orgs:
        if org['id'] not in exclude_ids:
            data_containers.append(org)
    return data_containers


# Hierarchy

def render_tree(top_nodes=None):
    '''Returns HTML for a hierarchy of all data containers'''
    context = {'model': model, 'session': model.Session}
    if not top_nodes:
        top_nodes = toolkit.get_action('group_tree')(
            context,
            data_dict={'type': 'data-container'})

    # Remove data deposit
    # TODO: https://github.com/okfn/ckanext-unhcr/issues/78
    depo = get_data_container_for_depositing()
    top_nodes = filter(lambda node: node['id'] != depo['id'], top_nodes)

    return _render_tree(top_nodes)


def _render_tree(top_nodes):
    html = '<ul class="hierarchy-tree-top">'
    for node in top_nodes:
        html += _render_tree_node(node)
    return html + '</ul>'


def _render_tree_node(node):
    html = '<a href="/data-container/{}">{}</a>'.format(
        node['name'], node['title'])
    if node['children']:
        html += '<ul class="hierarchy-tree">'
        for child in node['children']:
            html += _render_tree_node(child)
        html += '</ul>'

    if node['highlighted']:
        html = '<li id="node_{}" class="highlighted">{}</li>'.format(
            node['name'], html)
    else:
        html = '<li id="node_{}">{}</li>'.format(node['name'], html)
    return html


# Access restriction

def page_authorized():

    if (toolkit.c.controller == 'error' and
            toolkit.c.action == 'document' and
            toolkit.c.code and toolkit.c.code[0] != '403'):
        return True

    # TODO: remove request_reset and perform_reset when LDAP is integrated
    return (
        toolkit.c.userobj or
        (toolkit.c.controller == 'user' and
            toolkit.c.action in [
                'login', 'logged_in', 'request_reset', 'perform_reset',
                'logged_out', 'logged_out_page', 'logged_out_redirect'
                ]))


# Linked datasets

def get_linked_datasets_for_form(selected_ids=[], exclude_ids=[], context=None, user_id=None):
    context = context or {'model': model}
    user_id = user_id or toolkit.c.userobj.id

    # Prepare search query
    fq_list = []
    get_containers = toolkit.get_action('organization_list_for_user')
    containers = get_containers(context, {'id': user_id})
    for container in containers:
        fq_list.append('owner_org:{}'.format(container['id']))

    # Get search results
    search_datasets = toolkit.get_action('package_search')
    search = search_datasets(context, {
        'fq': ' OR '.join(fq_list),
        'include_private': True,
        'sort': 'organization asc, title asc',
    })

    # Get datasets
    orgs = []
    current_org = None
    selected_ids = selected_ids if isinstance(selected_ids, list) else selected_ids.strip('{}').split(',')
    for package in search['results']:

        if package['id'] in exclude_ids:
            continue
        if package['owner_org'] != current_org:
            current_org = package['owner_org']

            orgs.append({'text': package['organization']['title'], 'children': []})

        dataset = {'text': package['title'], 'value': package['id']}
        if package['id'] in selected_ids:
            dataset['selected'] = 'selected'
        orgs[-1]['children'].append(dataset)

    return orgs


def get_linked_datasets_for_display(value, context=None):
    context = context or {'model': model}

    # Get datasets
    datasets = []
    ids = utils.normalize_list(value)
    for id in ids:
        dataset = toolkit.get_action('package_show')(context, {'id': id})
        href = toolkit.url_for('dataset_read', id=dataset['name'], qualified=True)
        datasets.append({'text': dataset['title'], 'href': href})

    return datasets


# Deposited datasets

def get_data_container_for_depositing():
    NAME = 'data-deposit'
    context = {'model': model, 'ignore_auth': True}
    try:
        return toolkit.get_action('organization_show')(context, {'id': NAME})
    except toolkit.ObjectNotFound:
        log.error('Data Deposit is not created')
        return {'id': 'data-deposit'}


def get_dataset_validation_error_or_none(pkg_dict, context=None):
    context = context or {'model': model, 'session': model.Session, 'user': toolkit.c.user}
    if pkg_dict.get('type') == 'deposited-dataset':
        pkg_dict = convert_deposited_dataset_to_regular_dataset(pkg_dict)
    package_plugin = lib_plugins.lookup_package_plugin('dataset')
    schema = package_plugin.update_package_schema()
    data, errors = lib_plugins.plugin_validate(
        package_plugin, context, pkg_dict, schema, 'package_update')
    errors.pop('owner_org', None)
    return ValidationError(errors) if errors else None


def convert_deposited_dataset_to_regular_dataset(pkg_dict):
    pkg_dict = pkg_dict.copy()
    pkg_dict['type'] = 'dataset'
    pkg_dict['owner_org'] = pkg_dict['owner_org_dest']
    del pkg_dict['owner_org_dest']
    return pkg_dict
