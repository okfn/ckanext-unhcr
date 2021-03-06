import logging
import os
import re
from urllib import quote
from jinja2 import Markup, escape
from ckan import model
from ckan.lib import uploader
from operator import itemgetter
from ckan.logic import ValidationError
from ckan.plugins import toolkit
import ckan.lib.helpers as core_helpers
import ckan.lib.plugins as lib_plugins
from ckanext.hierarchy import helpers as hierarchy_helpers
from ckanext.scheming.helpers import (
    scheming_get_dataset_schema, scheming_field_by_name
)
from ckanext.unhcr import utils
from ckanext.unhcr import __VERSION__
from ckanext.unhcr.models import AccessRequest


log = logging.getLogger(__name__)

# Core overrides

@core_helpers.core_helper
def new_activities(*args, **kwargs):
    try:
        return core_helpers.new_activities(*args, **kwargs)
    except toolkit.NotAuthorized:
        return 0


@core_helpers.core_helper
def dashboard_activity_stream(*args, **kwargs):
    try:
        return core_helpers.dashboard_activity_stream(*args, **kwargs)
    except toolkit.NotAuthorized:
        return []


@core_helpers.core_helper
def url_for(*args, **kw):
    return core_helpers.url_for(*args, **kw)


# General

def get_data_container(id):
    context = {'model': model, 'ignore_auth': True}
    return toolkit.get_action('organization_show')(context, {'id': id})


def get_all_data_containers(
    exclude_ids=None,
    include_ids=None,
    include_unknown=False,
    userobj=None,
    dataset=None,
):
    if not exclude_ids:
        exclude_ids = []
    if not include_ids:
        include_ids = []
    include_ids = [id_ for id_ in include_ids if id_ and id_ != 'unknown']
    if not userobj:
        userobj = toolkit.c.userobj

    data_containers = []
    context = {'model': model, 'ignore_auth': True}
    orgs = toolkit.get_action('organization_list_all_fields')(context, {})

    for org in orgs:
        if org['id'] in exclude_ids:
            continue

        if org['approval_status'] != u'approved':
            continue

        if org['id'] in include_ids:
            data_containers.append(org)
            continue

        if userobj.external and (
            'visible_external' not in org or not org['visible_external']
        ):
            continue

        if (
            # we're editing an existing dataset, not creating a new one
            dataset

            # curators and sysadmins can always change the target to anything
            and not user_is_curator(userobj)
            and not userobj.sysadmin

            # external users can always change the target of their own dataset to any visible_external container
            and not userobj.external

            # if I'm editing my own deposit, I can always change the target to anything
            and 'creator_user_id' in dataset and dataset['creator_user_id'] != userobj.id
        ):
            user_orgs = toolkit.get_action('organization_list_for_user')(
                context,
                {'id': userobj.id, "permission": "admin"}
            )
            user_orgs_ids = [o['id'] for o in user_orgs]
            if org['id'] not in user_orgs_ids:
                continue

        data_containers.append(org)

    if include_unknown:
        data_containers.insert(0, {
            'id': 'unknown',
            'name': 'unknown',
            'title': 'Unknown',
            'display_name': 'Unknown',
        })
    return data_containers


def get_dataset_count():
    return toolkit.get_action('package_search')(
        {}, {'fq': 'dataset_type:dataset', 'rows': 1})['count']


# Hierarchy

def get_allowable_parent_groups(group_id):
    deposit = get_data_deposit()
    groups = hierarchy_helpers.get_allowable_parent_groups(group_id)
    groups = filter(lambda group: group.name != deposit.get('name'), groups)
    return groups


def render_tree(top_nodes=None):
    '''Returns HTML for a hierarchy of all data containers'''
    context = {'model': model, 'session': model.Session}
    if not top_nodes:
        top_nodes = toolkit.get_action('group_tree')(
            context,
            data_dict={'type': 'data-container'})

    # Remove data deposit
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
    allowed_controllers = [
        'user',  # most actions are defined in the core 'user' blueprint
        'unhcr_user',  # we override some actions in the 'unhcr_user' blueprint
    ]
    allowed_actions = [
        'logged_in',
        'logged_out',
        'logged_out_page',
        'logged_out_redirect',
        'login',
        'perform_reset',
        'register',
        'request_reset',
    ]
    return (
        toolkit.c.userobj
        or (
            toolkit.c.controller in allowed_controllers
            and toolkit.c.action in allowed_actions
        )
        or toolkit.request.path == '/service/login'
    )


def get_came_from_param():
    return toolkit.request.environ.get('CKAN_CURRENT_URL', '')


def user_is_curator(userobj=None):
    if not userobj:
        userobj = toolkit.c.userobj
    group = get_data_deposit()
    try:
        users = toolkit.get_action('member_list')(
            { 'ignore_auth': True },
            { 'id': group['id'] }
        )
    except toolkit.ObjectNotFound:
        return False
    user_ids = [u[0] for u in users]
    user_id = userobj.id
    return user_id in user_ids


def user_is_container_admin(user=None):
    if not user:
        user = toolkit.c.user
    orgs = toolkit.get_action("organization_list_for_user")(
        {"user": user},
        {"id": user, "permission": "admin"}
    )
    return len(orgs) > 0


# Linked datasets

def get_linked_datasets_for_form(selected_ids=[], exclude_ids=[], context=None, user_id=None):
    context = context or {'model': model}
    user_id = user_id or toolkit.c.userobj.id

    # Prepare search query
    fq_list = []
    get_containers = toolkit.get_action('organization_list_for_user')
    containers = get_containers(context, {'id': user_id})
    deposit = get_data_deposit()
    fq_list = [
        "owner_org:{}".format(container["id"])
        for container in containers
        if container["id"] != deposit["id"]
    ]

    # Get search results
    search_datasets = toolkit.get_action('package_search')
    search = search_datasets(context, {
        'fq': ' OR '.join(fq_list),
        'include_private': True,
        'sort': 'organization asc, title asc',
        'rows': 1000,
    })

    # Get datasets
    orgs = []
    current_org = None
    selected_ids = selected_ids if isinstance(selected_ids, list) else selected_ids.strip('{}').split(',')
    for package in search['results']:

        if package['id'] in exclude_ids:
            continue
        if package.get('owner_org') and package.get('owner_org') != current_org:
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


# Access requests

def get_pending_requests_total(context=None):
    context = context or {'model': model, 'user': toolkit.c.user}
    total = 0

    try:
        container_requests = toolkit.get_action('container_request_list')(
            context, {'all_fields': False}
        )
        total += container_requests['count']
    except (toolkit.NotAuthorized, toolkit.ObjectNotFound):
        pass

    try:
        access_requests = toolkit.get_action('access_request_list_for_user')(
            context, {}
        )
        total += len(access_requests)
    except (toolkit.NotAuthorized, toolkit.ObjectNotFound):
        pass

    return total


def get_existing_access_request(user_id, object_id, status):
    return model.Session.query(AccessRequest).filter(
        AccessRequest.user_id==user_id,
        AccessRequest.object_id==object_id,
        AccessRequest.status==status
    ).all()


def get_access_request_for_user(user_id):
    return model.Session.query(AccessRequest).filter(
        AccessRequest.object_id==user_id,
        AccessRequest.object_type=='user',
    ).one_or_none()


# Deposited datasets

cached_deposit = None
def get_data_deposit():
    '''
    Return the dict of the underlying organization for the data deposit

    This function uses a cache so it's OK to call it multiple times

    :returns: The data deposit organization dict
    :rtype: dict
    '''

    # Check cache
    deposit = None
    global cached_deposit
    if not toolkit.config.get('testing'):
        deposit = cached_deposit

    # Load from db
    if deposit is None:
        try:
            context = {'model': model, 'ignore_auth': True}
            deposit = toolkit.get_action('organization_show')(
                context, {'id': 'data-deposit'})
            if not toolkit.config.get('testing'):
                cached_deposit = deposit
        except toolkit.ObjectNotFound:
            log.error('Data Deposit is not created')
            deposit = {'id': 'data-deposit', 'name': 'data-deposit'}

    return deposit


def get_data_curation_users(dataset):
    '''
    Return a list of users that are allowed to curate a particular dataset.
    This includes:

    * Sysadmins
    * Curation team (Admins and Editors of the data-deposit org)
    * Admins of the target data container

    :param dataset: The dataset that needs to be curated
    :type dataset: dict

    :returns: A list of user dicts that can curate the dataset
    :rtype: list
    '''
    context = {'model': model, 'ignore_auth': True}
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

    container_admins = []
    owner_org_dest = dataset.get('owner_org_dest')
    if owner_org_dest and owner_org_dest != 'unknown':
        container_admins = toolkit.get_action('member_list')(context, {
            'id': owner_org_dest,
            'capacity': 'admin',
            'object_type': 'user',
        })

    # Get users
    users = []
    for item in depadmins + curators + container_admins:
        user = toolkit.get_action('user_show')(context, {'id': item[0]})
        user.pop('default_containers', None)
        users.append(user)

    users = [dict(tup) for tup in {tuple(u.items()) for u in users}]  # de-dupe

    # Sort users
    users = list(sorted(users, key=itemgetter('display_name', 'name')))

    return users


def get_deposited_dataset_user_curation_status(dataset, user_id):
    '''
    Returns an object describing the status of a given dataset and user
    in the context of the data deposit.

    :param dataset: A deposited dataset dict
    :type dataset: dict
    :param user_id: The id of the relevant user
    :type user_id: string

    :returns: An object with the following keys:

        * `state`: The curation state of the dataset (eg "review", "submitted",
            "draft", etc)
        * `active`: Whether the status of the dataset is "active"
        * `final_review`: Whether the depositor requested a final review
        * `error`: Validation errors of the deposited dataset
        * `role`: Role that the provided user has on this particular dataset,
            see :py:func:`~ckanext.unhcr.helpers.get_deposited_dataset_user_curation_role`
        * `is_depositor`: Whether the provided user was the original depositor
        * `is_curator`: Whether the provided user is the assigned curator to the dataset
        * `actions`: List of allowed actions for the provided user,
            see :py:func:`~ckanext.unhcr.helpers.get_deposited_dataset_user_curation_actions`
        * `contacts`: An object with the following keys (
            see :py:func:`~ckanext.unhcr.helpers.get_deposited_dataset_user_contact`
            `depositor`: an object with the original depositor user details
            `curator`: an object with the assigned curator user details
    :rtype: dict
    '''
    deposit = get_data_deposit()
    context = {'user': user_id, 'model': model, 'session': model.Session}

    # General
    status = {}
    status['error'] = get_dataset_validation_error_or_none(dataset, context)
    status['role'] = get_deposited_dataset_user_curation_role(user_id, dataset)
    status['state'] = dataset['curation_state']
    status['final_review'] = dataset.get('curation_final_review')
    status['active'] = dataset['state'] == 'active'

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


def get_deposited_dataset_user_curation_role(user_id, dataset=None):
    '''
    Returns the role that the provided user has in the context of the
    data deposit.

    If a dataset dict is provided, the admins of the organization the
    dataset belongs to are also considered when deciding the user role.

    The available roles are:

    * admin: Can manage members of the data deposit
    * curator: Can edit and manage deposited datasets
    * container admin: Can edit and manage deposited datasets (that are
        targetted to one of the admins the user is admin of)
    * depositor: Can create new deposited datasets
    * user: No permissions available on the data deposit

    :param user_id: The user that we want to know the role of in the data
        deposit
    :type user_id: string

    :returns: The role the user has
    :rtype: string
    '''
    action = toolkit.get_action('organization_list_for_user')
    context = {'model': model, 'user': user_id}
    deposit = get_data_deposit()

    admin_orgs = action(context, {'permission': 'admin'})
    admin_orgs_ids = [org['id'] for org in admin_orgs]

    member_orgs = action(context, {'permission': 'create_dataset'})
    member_org_ids = [org['id'] for org in member_orgs]


    if deposit['id'] in admin_orgs_ids:
        return 'admin'

    if deposit['id'] in member_org_ids:
        return 'curator'

    if not dataset:
        if len(admin_orgs_ids) > 0:
            return 'container admin'
        return 'depositor'

    if (
        dataset['owner_org_dest'] != 'unknown'
        and dataset['owner_org_dest'] in admin_orgs_ids
    ):
        return 'container admin'

    if dataset['creator_user_id'] == user_id:
        return 'depositor'

    return 'user'


def get_deposited_dataset_user_curation_actions(status):
    '''
    Return a list of actions that the user is allowed to perform on a deposited
    dataset

    :param status: An object containing the following keys: "state", "is_depositor",
        "active", "role", "error", "final_review"
        (see :py:func:`~ckanext.unhcr.helpers.get_deposited_dataset_user_curation_status`
        for details.
    :type status: dict

    :returns: A list of allowed actions. Possible values are: "edit", "submit", "withdraw",
        "reject", "request_changes", "assign", "request_review", "approve"
    :rtype: list
    '''
    actions = []

    # Draft
    if status['state'] == 'draft':
        if status['is_depositor']:
            actions.extend(['edit'])
            if status['active']:
                actions.extend(['submit', 'withdraw'])

    # Submitted
    if status['state'] == 'submitted':
        if status['role'] in ['admin', 'curator', 'container admin']:
            actions.extend(['edit', 'reject'])
            if status['role'] == 'admin':
                actions.extend(['assign'])
            if status['error']:
                actions.extend(['request_changes'])
            else:
                if status['final_review']:
                    actions.extend(['request_review'])
                else:
                    actions.extend(['approve'])

    # Review
    if status['state'] == 'review':
        if status['is_depositor']:
            actions.extend(['request_changes'])
            if not status['error']:
                actions.extend(['approve'])

    return actions


def get_deposited_dataset_user_contact(user_id=None):
    '''
    Returns selected attributes from the provided user id, or None if not found

    :param user_id: The provided user id
    :type user_id: string

    :returns: A user dict with the following keys: "id", "name", "display_name",
        "title" (same as "display_name"), "email", "external"
    :rtype: dict
    '''

    # Return none (no id)
    if not user_id:
        return None

    # Return none (no user)
    userobj = model.User.get(user_id)
    if not userobj:
        return None

    # Return contact
    return {
        'id': getattr(userobj, 'id'),
        'title': getattr(userobj, 'display_name'),
        'display_name': getattr(userobj, 'display_name'),
        'name': getattr(userobj, 'name'),
        'email': getattr(userobj, 'email'),
        'external': getattr(userobj, 'external'),
    }


def get_dataset_validation_error_or_none(pkg_dict, context):
    # Convert dataset
    if pkg_dict.get('type') == 'deposited-dataset':
        pkg_dict = convert_deposited_dataset_to_regular_dataset(pkg_dict)

    # Validate dataset
    package_plugin = lib_plugins.lookup_package_plugin('dataset')
    schema = package_plugin.update_package_schema()
    data, errors = lib_plugins.plugin_validate(
        package_plugin, context, pkg_dict, schema, 'package_update')
    errors.pop('owner_org', None)
    if data.get('owner_org') == 'unknown':
        errors['owner_org_dest'] = ['Missing Value']

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
        try:
            fields = sorted(error_dict['resources'][index])
        except KeyError, IndexError:
            continue
        if fields:
            report['resources'].append({
                'id': resource['id'],
                'name': resource['name'],
                'fields': fields,
            })
    return report


def get_user_deposited_drafts():
    context = {'model': model, 'user': toolkit.c.user}

    # Get datasets
    fq_list = []
    fq_list.append('state:draft')
    fq_list.append('dataset_type:deposited-dataset')
    fq_list.append('creator_user_id:%s' % toolkit.c.userobj.id)
    data_dict = {'fq':  ' AND '.join(fq_list), 'include_drafts': True}
    datasets = toolkit.get_action('package_search')(context, data_dict)['results']

    return datasets


def get_default_container_for_user():
    context = {'model': model, 'user': toolkit.c.user}
    user = toolkit.get_action('user_show')(context, {'id': toolkit.c.user})
    if len(user['default_containers']) > 0:
        return user['default_containers'][0]
    return 'unknown'


# Internal activity

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


def download_resource_renderer(context, activity):
    resource_name = activity['data']['name'] or 'Unnamed resource'
    resource_link = toolkit.url_for(
        action='resource_read',
        controller='package',
        id=activity['object_id'],
        resource_id=activity['data']['id']
    )
    return "{actor} downloaded " + core_helpers.tags.link_to(resource_name, resource_link)

def custom_activity_renderer(context, activity):
    '''
    Before CKAN 2.9 the only way to customize the activty stream snippets was to
    monkey patch a renderer, as we do here.
    '''
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
        output =  toolkit._("{actor} assigned %s as Curator for dataset {dataset}" % curator_link)
    elif activity_name == 'curator_removed':
        output =  toolkit._("{actor} removed the assigned Curator from dataset {dataset}")
    elif activity_name == 'changes_requested':
        output =  toolkit._("{actor} unlocked {dataset} for further changes by the Depositor")
    elif activity_name == 'final_review_requested':
        output =  toolkit._("{actor} requested a final review of {dataset} from the Depositor")
    elif activity_name == 'dataset_rejected':
        output = toolkit._("{actor} rejected dataset {dataset} for publication")
    elif activity_name == 'dataset_withdrawn':
        output = toolkit._("{actor} withdrawn dataset {dataset} from the data deposit")
    elif activity_name == 'dataset_approved':
        output = toolkit._("{actor} approved dataset {dataset} for publication")

    if activity['data'].get('message'):
        output = output + ' with the following message: <q class="curation-message">%s</q>' % activity['data']['message']

    return output


# Publishing

def convert_dataset_to_microdata_survey(dataset, nation, repoid):

    # general
    survey = {
      'access_policy': 'na',
      'published': 0,
      'overwrite': 'no',
      'study_desc': {
          'study_info': {},
          'method': {
              'data_collection': {},
          },
      },
    }

    # repositoryid
    if repoid:
        survey['repositoryid'] = repoid.upper()

    # title_statement
    survey['study_desc']['title_statement'] = {
        'idno': dataset['name'].upper(),
        'title': dataset.get('title'),
    }

    # authority_entity
    survey['study_desc']['authoring_entity'] = [
        {
            'name': 'Office of the High Commissioner for Refugees',
            'affiliation': 'UNHCR'
        }
    ]

    # distribution_statement
    if dataset.get('maintainer'):
        survey['study_desc']['distribution_statement'] = {
            'contact': [{
                'name': dataset.get('maintainer'),
                'email': dataset.get('maintainer_email'),
            }]
        }

    # version_statement
    if dataset.get('version'):
        survey['study_desc']['version_statement'] =  {
            'version': dataset.get('version'),
        }

    # keywords
    if dataset.get('tags', []):
        survey['study_desc']['study_info']['keywords'] = []
        for tag in dataset.get('tags', []):
            survey['study_desc']['study_info']['keywords'].append(
                {'keyword': tag.get('display_name')})

    # topics
    if dataset.get('keywords', []):
        survey['study_desc']['study_info']['topics'] = []
        for value in dataset.get('keywords', []):
            survey['study_desc']['study_info']['topics'].append(
                {'topic': get_choice_label('keywords', value)})

    # abstract
    if dataset.get('notes'):
        survey['study_desc']['study_info']['abstract'] = dataset.get('notes').strip()

    # coll_dates
    if dataset.get('date_range_start') and dataset.get('date_range_end'):
        survey['study_desc']['study_info']['coll_dates'] = [
            {
              'start': dataset.get('date_range_start'),
              'end': dataset.get('date_range_end'),
            }
        ]

    # nation
    if nation:
        survey['study_desc']['study_info']['nation'] = [
            {'name': name.strip()} for name in nation.split(',')
        ]

    # geog_coverage
    if dataset.get('geog_coverage'):
        survey['study_desc']['study_info']['geog_coverage'] = dataset.get('geog_coverage')

    # analysis_unit
    if dataset.get('unit_of_measurement'):
        survey['study_desc']['study_info']['analysis_unit'] = dataset.get('unit_of_measurement')

    # data_collectors
    if dataset.get('data_collector', ''):
        survey['study_desc']['method']['data_collection']['data_collectors'] = []
        for value in normalize_list(dataset.get('data_collector', '')):
            survey['study_desc']['method']['data_collection']['data_collectors'].append(
                {'name': value})

    # sampling_procedure
    sampling_procedure = None
    if dataset.get('sampling_procedure', []):
        values = []
        for value in dataset.get('sampling_procedure', []):
            values.append(get_choice_label('sampling_procedure', value))
        survey['study_desc']['method']['data_collection']['sampling_procedure'] = ', '.join(values)
    elif dataset.get('sampling_procedure_notes'):
        survey['study_desc']['method']['data_collection']['sampling_procedure'] = dataset.get('sampling_procedure_notes').strip()

    # coll_mode
    if dataset.get('data_collection_technique'):
        survey['study_desc']['method']['data_collection']['coll_mode'] = get_choice_label(
            'data_collection_technique', dataset.get('data_collection_technique'))

    # coll_situation
    if dataset.get('data_collection_notes'):
        survey['study_desc']['method']['data_collection']['coll_situation'] = dataset.get('data_collection_notes').strip()

    # weight
    if dataset.get('weight_notes'):
        survey['study_desc']['method']['data_collection']['weight'] = dataset.get('weight_notes').strip()

    # cleaning_operations
    if dataset.get('clean_ops_notes'):
        survey['study_desc']['method']['data_collection']['cleaning_operations'] = dataset.get('clean_ops_notes').strip()

    # analysis_info
    if dataset.get('response_rate_notes'):
        survey['study_desc']['method']['analysis_info'] = {
            'response_rate': dataset.get('response_rate_notes').strip(),
          }

    return survey


def convert_resource_to_microdata_resource(resource):
    TYPES_MAPPING = {
        'microdata': 'dat/micro',
        'questionnaire': 'doc/qst',
        'report': 'doc/rep',
        'sampling_methodology': 'doc/oth',
        'infographics': 'doc/oth',
        'attachment': 'doc/oth',
    }

    # general
    md_resource = {
        'title': resource.get('name') or 'Unnamed resource',
        'dctype': TYPES_MAPPING[resource.get('file_type', 'attachment')],
    }

    # dcformat
    if resource.get('format'):
        md_resource['dcformat'] = resource.get('format').lower()

    # description
    if resource.get('description'):
        md_resource['description'] = resource.get('description')

    return md_resource


def get_microdata_collections():
    context = {'user': toolkit.c.user}
    try:
        return toolkit.get_action('package_get_microdata_collections')(context, {})
    except (toolkit.NotAuthorized, RuntimeError):
        return None


# Misc

def current_path(action=None):
    path = toolkit.request.path
    if action == '/dataset/new':
        path = '/dataset/new'
    if path.startswith('/dataset/copy') or path.startswith('/deposited-dataset/copy'):
        path = '/dataset/new'
    return path


def get_field_label(name, is_resource=False):
    schema = scheming_get_dataset_schema('deposited-dataset')
    fields = schema['resource_fields'] if is_resource else schema['dataset_fields']
    field = scheming_field_by_name(fields, name)
    if field:
        return field.get('label', name)
    else:
        log.warning('Could not get field {} from deposited-dataset schema'.format(name))


def get_choice_label(name, value, is_resource=False):
    schema = scheming_get_dataset_schema('deposited-dataset')
    fields = schema['resource_fields'] if is_resource else schema['dataset_fields']
    field = scheming_field_by_name(fields, name)
    if field:
        for choice in field.get('choices', []):
            if choice.get('value') == value:
                return choice.get('label')
        return value
    else:
        log.warning('Could not get field {} from deposited-dataset schema'.format(name))


def normalize_list(value):
    # It takes into account that ''.split(',') == ['']
    if not value:
        return []
    if isinstance(value, list):
        return value
    return value.strip('{}').split(',')


def can_download(package_dict):
    try:
        context = {'user': toolkit.c.user}
        resource_dict = package_dict.get('resources', [])[0]
        toolkit.check_access('resource_download', context, resource_dict)
        return True
    except (toolkit.NotAuthorized, toolkit.ObjectNotFound, IndexError):
        return False


def get_resource_file_path(resource):
    if resource.get(u'url_type') == u'upload':
        upload = uploader.get_resource_uploader(resource)
        return upload.get_path(resource[u'id'])
    return None


def add_file_name_suffix(file_name, file_suffix):
    try:
        file_base, file_extension = file_name.split('.', 1)
        return  '%s (%s).%s' % (file_base, file_suffix, file_extension)
    except ValueError:
        return  '%s (%s)' % (file_name, file_suffix)


def get_sysadmins():
    return model.Session.query(model.User).filter(model.User.sysadmin==True).all()


def get_ridl_version():
    return __VERSION__


def get_envname():
    envname = os.environ.get('ENV_NAME')
    if not envname:
        return 'dev'
    return envname.lower()


def get_google_analytics_id():
    return toolkit.config.get('ckanext.unhcr.google_analytics_id', '')


def get_max_resource_size():
    return toolkit.config.get('ckan.max_resource_size', 10)


_paragraph_re = re.compile(r'(?:\r\n|\r(?!\n)|\n){2,}')

def nl_to_br(text):
    result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', Markup('<br>\n'))
                          for p in _paragraph_re.split(escape(text)))
    return Markup(result)
