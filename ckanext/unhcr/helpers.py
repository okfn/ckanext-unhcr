import re
import logging
from ckan import model
from operator import itemgetter
from collections import OrderedDict
from ckan.logic import ValidationError
from ckan.plugins import toolkit
import ckan.lib.helpers as core_helpers
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
    deposit = get_data_deposit()
    top_nodes = filter(lambda node: node['id'] != deposit['id'], top_nodes)

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

def get_data_deposit():
    try:
        context = {'model': model, 'ignore_auth': True}
        return toolkit.get_action('organization_show')(context, {'id': 'data-deposit'})
    except toolkit.ObjectNotFound:
        log.error('Data Deposit is not created')
        return {'id': 'data-deposit'}


def get_data_curation_users(context=None):
    context = context or {'model': model, 'user': toolkit.c.user}
    deposit = get_data_deposit()

    # Get depadmins
    depadmins = toolkit.get_action('member_list')(context, {
        'id': deposit['id'],
        'capacity': 'admin',
        'object_type': 'user',
    })

    # Get curators
    curators = toolkit.get_action('member_list')(context, {
        'id': deposit['id'],
        'capacity': 'editor',
        'object_type': 'user',
    })

    # Get users
    users = []
    for item in depadmins + curators:
        user = toolkit.get_action('user_show')(context, {'id': item[0]})
        users.append(user)

    # Sort users
    users = list(sorted(users,
        key=itemgetter('display_name')))

    return users


def get_deposited_dataset_user_curation_status(dataset, user_id):
    deposit = get_data_deposit()

    # General
    status = {}
    status['error'] = get_dataset_validation_error_or_none(dataset)
    status['role'] = get_deposited_dataset_user_curation_role(user_id)
    status['state'] = dataset['curation_state']

    # is_depositor/curator
    status['is_depositor'] = dataset.get('creator_user_id') == user_id
    status['is_curator'] = dataset.get('curator_id') == user_id

    # actions
    status['actions'] = get_deposited_dataset_user_curation_actions(status)

    # contacts
    status['contacts'] = {
        'depositor': get_deposited_dataset_user_contact(dataset.get('creator_user_id')),
        'curator': get_deposited_dataset_user_contact(dataset.get('curator_id')),
    }

    return status


def get_deposited_dataset_user_curation_role(user_id):
    action = toolkit.get_action('organization_list_for_user')
    context = {'model': model, 'user': user_id}
    deposit = get_data_deposit()

    # Admin
    orgs = action(context, {'permission': 'admin'})
    if deposit['id'] in [org['id'] for org in orgs]:
        return 'admin'

    # Curator
    orgs = action(context, {'permission': 'create_dataset'})
    if deposit['id'] in [org['id'] for org in orgs]:
        return 'curator'

    # Depositor
    return 'depositor'


def get_deposited_dataset_user_curation_actions(status):
    actions = []

    # Draft
    if status['state'] == 'draft':
        if status['is_depositor']:
            actions.extend(['edit', 'submit', 'withdraw'])

    # Submitted
    if status['state'] == 'submitted':
        if status['role'] in ['admin', 'curator']:
            actions.extend(['edit', 'reject'])
            if status['role'] == 'admin':
                actions.extend(['assign'])
            if status['error']:
                actions.extend(['request_changes'])
            else:
                actions.extend(['request_review'])
                actions.extend(['approve'])

    # Review
    if status['state'] == 'review':
        if status['is_depositor']:
            actions.extend(['request_changes'])
            if not status['error']:
                actions.extend(['approve'])

    return actions


def get_deposited_dataset_user_contact(user_id=None):

    # Return none (no id)
    if not user_id:
        return None

    # Return none (no user)
    try:
        user = toolkit.get_action('user_show')({'ignore_auth': True}, {'id': user_id})
    except toolkit.ObjectNotFound:
        return None

    # Return contact
    return {
        'title': user.get('display_name'),
        'email': user.get('email'),
    }


def get_dataset_validation_error_or_none(pkg_dict, context=None):
    context = context or {'model': model, 'session': model.Session, 'user': toolkit.c.user}

    # Convert dataset
    if pkg_dict.get('type') == 'deposited-dataset':
        pkg_dict = convert_deposited_dataset_to_regular_dataset(pkg_dict)

    # Validate dataset
    package_plugin = lib_plugins.lookup_package_plugin('dataset')
    schema = package_plugin.update_package_schema()
    data, errors = lib_plugins.plugin_validate(
        package_plugin, context, pkg_dict, schema, 'package_update')
    errors.pop('owner_org', None)

    return ValidationError(errors) if errors else None


def convert_deposited_dataset_to_regular_dataset(pkg_dict):
    pkg_dict = pkg_dict.copy()

    # Update fields
    pkg_dict['type'] = 'dataset'
    pkg_dict['owner_org'] = pkg_dict['owner_org_dest']

    # Remove fields
    pkg_dict.pop('owner_org_dest', None)
    pkg_dict.pop('curation_state', None)
    pkg_dict.pop('curator_id', None)

    return pkg_dict


def get_dataset_validation_report(pkg_dict, error_dict):
    report = {}

    # Dataset
    report['dataset'] = {
        'fields': sorted([field for field in error_dict if field != 'resources']),
    }

    # Resources
    report['resources'] = []
    for index, resource in enumerate(pkg_dict.get('resources', [])):
        report['resources'].append({
            'id': resource['id'],
            'name': resource['name'],
            'fields': sorted(error_dict['resources'][index]),
        })

    return report


def get_field_pretty_name(field_name):
    # https://github.com/ckan/ckan/blob/master/ckan/logic/__init__.py#L90
    field_name = field_name.replace('_', ' ').capitalize()
    field_name = re.sub('(?<!\w)[Uu]rl(?!\w)', 'URL', field_name)
    return field_name.replace('_', ' ')


def create_curation_activity(
        activity_type, dataset_id, dataset_name, user_id,
        message=None, **kwargs):
    activity_context = {'ignore_auth': True}
    data_dict = {
        'user_id': user_id,
        'object_id': dataset_id,
        'activity_type': 'changed package',
        'data': {
            'curation_activity': activity_type,
            'package': {'name': dataset_name, 'id': dataset_id},
        }
    }
    if message:
        data_dict['data']['message'] = message
    if kwargs:
        for key, value in kwargs.iteritems():
            data_dict['data'][key] = value

    toolkit.get_action('activity_create')(activity_context, data_dict)


def custom_activity_renderer(context, activity):
    '''
    Before CKAN 2.9 the only way to customize the activty stream snippets was to
    monkey patch a renderer, as we do here.
    '''
    log.error(activity)
    if 'curation_activity' not in activity.get('data', {}):
        # Default core one
        return toolkit._("{actor} updated the dataset {dataset}")

    activity_name = activity['data']['curation_activity']

    output = ''

    if activity_name == 'dataset_deposited':
        output =  toolkit._("{actor} deposited dataset {dataset}")
    elif activity_name == 'dataset_submitted':
        output =  toolkit._("{actor} submitted dataset {dataset} for curation")
    elif activity_name == 'curator_assigned':
        curator_link = core_helpers.tags.link_to(
	    activity['data']['curator_name'],
            toolkit.url_for(
                controller='user', action='read', id=activity['data']['curator_name'])
	)
        output =  toolkit._("{actor} assigned %s as curator for dataset {dataset}" % curator_link)
    elif activity_name == 'curator_removed':
        output =  toolkit._("{actor} removed the assigned curator from dataset {dataset}")
    elif activity_name == 'changes_requested':
        output =  toolkit._("{actor} unlocked {dataset} for further changes by the depositor")
    elif activity_name == 'final_review_requested':
        output =  toolkit._("{actor} requested a final review of {dataset} from the depositor")
    elif activity_name == 'dataset_rejected':
        output = toolkit._("{actor} rejected dataset {dataset} for publication")
    elif activity_name == 'dataset_withdrawn':
        output = toolkit._("{actor} withdrawn dataset {dataset} from the data deposit")
    elif activity_name == 'dataset_approved':
        output = toolkit._("{actor} approved dataset {dataset} for publication")

    if activity['data'].get('message'):
        output = output + ' with the following message: %s' % activity['data']['message']

    return output
