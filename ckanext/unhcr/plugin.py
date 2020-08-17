# encoding: utf-8
import os
import json
import logging

from ckan.common import config
import ckan.lib.helpers as core_helpers
from ckan.model import User
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.plugins import DefaultTranslation
from ckan.lib.plugins import DefaultPermissionLabels

# 🙈
import ckan.authz as authz
from ckan.lib.activity_streams import (
    activity_stream_string_functions,
    activity_stream_string_icons,
)

from ckanext.unhcr import actions, auth, blueprints, helpers, jobs, validators

from ckanext.scheming.helpers import scheming_get_dataset_schema
from ckanext.hierarchy.helpers import group_tree_section

log = logging.getLogger(__name__)

_ = toolkit._


INTERNAL_DOMAINS = ['unhcr.org']


def user_is_external(user):
    '''
    Returns True if user email is not in the managed internal domains.
    '''
    try:
        domain = user.email.split('@')[1]
    except AttributeError:
         # Internal sysadmin user does not have email
        if user.sysadmin:
            return False
        else:
            return True

    internal_domains = toolkit.aslist(
        toolkit.config.get('ckanext.unhcr.internal_domains', INTERNAL_DOMAINS),
        sep = ','
    )

    return domain not in internal_domains


def restrict_external(func):
    '''
    Decorator function to restrict external users to a small number of allowed_actions
    '''

    allowed_actions = [
        'package_search',
    ]

    def wrapper(action, context, data_dict=None):
        user = User.by_name(context.get('user'))
        if not user:
            return func(action, context, data_dict)
        if user.sysadmin:
            return func(action, context, data_dict)
        if context.get('ignore_auth'):
            return func(action, context, data_dict)
        if user.external and action not in allowed_actions:
            return {'success': False, 'msg': 'Not allowed to perform this action'}
        return func(action, context, data_dict)
    return wrapper


_url_for = core_helpers.url_for

def url_for(*args, **kw):
    url = _url_for(*args, **kw)

    if getattr(toolkit.c.userobj, 'external', None) and '/dataset/' in url:
        url = url.replace('/dataset/', '/deposited-dataset/')
    return url


class UnhcrPlugin(
        plugins.SingletonPlugin, DefaultTranslation, DefaultPermissionLabels):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITranslation)
    plugins.implements(plugins.IFacets)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.IRoutes, inherit=True)
    plugins.implements(plugins.IPermissionLabels)
    plugins.implements(plugins.IBlueprint)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'unhcr')

        # TODO: in CKAN 2.9 we can add `icon='hdd-o'` here
        # but not yet :(
        toolkit.add_ckan_admin_tab(config_, 'unhcr_search_index.index', 'Search Index')

        activity_stream_string_functions['changed package'] = helpers.custom_activity_renderer
        activity_stream_string_functions['download resource'] = helpers.download_resource_renderer
        activity_stream_string_icons['download resource'] = 'download'

        User.external = property(user_is_external)
        authz.is_authorized = restrict_external(authz.is_authorized)
        core_helpers.url_for = url_for

    def update_config_schema(self, schema):
        schema.update({
            'ckanext.unhcr.microdata_api_key': [
                toolkit.get_validator('ignore_missing'),
            ],
        })

        return schema

    # IRoutes

    def before_map(self, _map):

        # header
        # TODO: review header item creation
        controller = 'ckan.controllers.organization:OrganizationController'
        _map.connect('data-deposit', '/data-container/data-deposit', controller=controller, action='read', id='data-deposit')

        # data container
        controller = 'ckanext.unhcr.controllers.data_container:DataContainerController'
        _map.connect('/data-container/{id}/approve', controller=controller, action='approve')
        _map.connect('/data-container/{id}/reject', controller=controller, action='reject')
        _map.connect('data_container_membership', '/data-container/membership', controller=controller, action='membership', ckan_icon='user')
        _map.connect('data_container_membership_add', '/data-container/membership_add', controller=controller, action='membership_add', ckan_icon='user')
        _map.connect('data_container_membership_remove', '/data-container/membership_remove', controller=controller, action='membership_remove', ckan_icon='user')

        # deposited dataset
        controller = 'ckanext.unhcr.controllers.deposited_dataset:DepositedDatasetController'
        _map.connect('/deposited-dataset/{dataset_id}/approve', controller=controller, action='approve')
        _map.connect('/deposited-dataset/{dataset_id}/assign', controller=controller, action='assign')
        _map.connect('/deposited-dataset/{dataset_id}/request_changes', controller=controller, action='request_changes')
        _map.connect('/deposited-dataset/{dataset_id}/request_review', controller=controller, action='request_review')
        _map.connect('/deposited-dataset/{dataset_id}/reject', controller=controller, action='reject')
        _map.connect('/deposited-dataset/{dataset_id}/submit', controller=controller, action='submit')
        _map.connect('/deposited-dataset/{dataset_id}/withdraw', controller=controller, action='withdraw')

        # package

        # Re-add these core ones otherwise our route below will mask them
        _map.connect('search', '/dataset', controller='package', action='search', highlight_actions='index search')
        _map.connect('add dataset', '/dataset/new', controller='package', action='new')
        _map.connect('/dataset/{action}', controller='package',
                  requirements=dict(action='|'.join([
                      'list',
                      'autocomplete',
                      'search'
                  ])))

        # Re-add these DDI ones otherwise our route below will mask them
        _map.connect(
            '/dataset/import',
            controller='ckanext.ddi.controllers:ImportFromXml',
            action='import_form'
        )
        _map.connect(
            '/dataset/importfile',
            controller='ckanext.ddi.controllers:ImportFromXml',
            action='run_import'
        )

        controller = 'ckanext.unhcr.controllers.extended_package:ExtendedPackageController'
        _map.connect('/dataset/{id}', controller=controller, action='read')
        _map.connect('/dataset/publish/{id}', controller=controller, action='publish')
        _map.connect('/dataset/copy/{id}', controller=controller, action='copy')
        _map.connect('/dataset/{id}/resource_copy/{resource_id}', controller=controller, action='resource_copy')
        _map.connect('/dataset/{id}/publish_microdata', controller=controller, action='publish_microdata')
        _map.connect('/dataset/{id}/request_access', controller=controller, action='request_access', conditions={'method': ['POST']})
        _map.connect('dataset_internal_activity', '/dataset/internal_activity/{dataset_id}', controller=controller, action='activity')
        _map.connect('deposited-dataset_internal_activity', '/deposited-dataset/internal_activity/{dataset_id}', controller=controller, action='activity')
        if 'cloudstorage' not in config['ckan.plugins']:
            _map.connect('/dataset/{id}/resource/{resource_id}/download', controller=controller, action='resource_download')
            _map.connect('/dataset/{id}/resource/{resource_id}/download/{filename}', controller=controller, action='resource_download')
        else:
            controller='ckanext.unhcr.controllers.extended_storage:ExtendedStorageController'
            _map.connect('/dataset/{id}/resource/{resource_id}/download', controller=controller, action='resource_download')
            _map.connect('/dataset/{id}/resource/{resource_id}/download/{filename}', controller=controller, action='resource_download')


        # organization

        # Re-add this core one otherwise our route below will mask it
        _map.connect('data-container_new', '/data-container/new',
                        controller='organization', action='new')

        controller = 'ckanext.unhcr.controllers.extended_organization:ExtendedOrganizationController'
        _map.connect('/data-container/{id}', controller=controller, action='read')

        # user
        controller = 'ckanext.unhcr.controllers.extended_user:ExtendedUserController'
        _map.connect('dashboard.requests', '/dashboard/requests', controller=controller, action='list_requests', ckan_icon='spinner')

        return _map

    # IFacets

    def _facets(self, facets_dict):
        if 'groups' in facets_dict:
            del facets_dict['groups']

        facets_dict['vocab_data_collector'] = _('Data Collector')
        facets_dict['vocab_keywords'] = _('Keywords')
        facets_dict['vocab_sampling_procedure'] = _('Sampling Procedure')
        facets_dict['vocab_operational_purpose_of_data'] = _(
            'Operational purpose of data')
        facets_dict['vocab_process_status'] = _('Process Status')
        facets_dict['vocab_identifiability'] = _('Identifiability')
        facets_dict['vocab_data_collection_technique'] = _(
            'Data Collection Technique')

        return facets_dict

    def dataset_facets(self, facets_dict, package_type):
        return self._facets(facets_dict)

    def group_facets(self, facets_dict, group_type, package_type):
        return self._facets(facets_dict)

    def organization_facets(self, facets_dict, organization_type, package_type):
        # TODO: optimize data deposit calls
        deposit = helpers.get_data_deposit()
        if deposit['id'] == getattr(toolkit.c.group, 'id', None):
            facets_dict.clear()
            facets_dict['curation_state'] = _('State')
            facets_dict['curator_display_name'] = _('Curator')
            facets_dict['depositor_display_name'] = _('Depositor')
            facets_dict['owner_org_dest_display_name'] = _('Data Container')
            return facets_dict
        else:
            return self._facets(facets_dict)

    # ITemplateHelpers

    def get_helpers(self):
        return {
            # Core overrides
            'new_activities': helpers.new_activities,
            'dashboard_activity_stream': helpers.dashboard_activity_stream,
            # General
            'get_data_container': helpers.get_data_container,
            'get_all_data_containers': helpers.get_all_data_containers,
            'get_dataset_count': helpers.get_dataset_count,
            # Hierarchy
            'get_allowable_parent_groups': helpers.get_allowable_parent_groups,
            'render_tree': helpers.render_tree,
            # Access restriction
            'page_authorized': helpers.page_authorized,
            'get_came_from_param': helpers.get_came_from_param,
            'user_is_curator': helpers.user_is_curator,
            'user_is_container_admin': helpers.user_is_container_admin,
            # Linked datasets
            'get_linked_datasets_for_form': helpers.get_linked_datasets_for_form,
            'get_linked_datasets_for_display': helpers.get_linked_datasets_for_display,
            # Access requests
            'get_pending_requests_total': helpers.get_pending_requests_total,
            'get_existing_access_request': helpers.get_existing_access_request,
            # Deposited datasets
            'get_data_deposit': helpers.get_data_deposit,
            'get_data_curation_users': helpers.get_data_curation_users,
            'get_deposited_dataset_user_curation_status': helpers.get_deposited_dataset_user_curation_status,
            'get_deposited_dataset_user_curation_role': helpers.get_deposited_dataset_user_curation_role,
            'get_dataset_validation_report': helpers.get_dataset_validation_report,
            'get_user_deposited_drafts': helpers.get_user_deposited_drafts,
            # Microdata
            'get_microdata_collections': helpers.get_microdata_collections,
            # Misc
            'current_path': helpers.current_path,
            'normalize_list': helpers.normalize_list,
            'get_field_label': helpers.get_field_label,
            'can_download': helpers.can_download,
            'get_choice_label': helpers.get_choice_label,
            'get_ridl_version': helpers.get_ridl_version,
            'get_envname': helpers.get_envname,
            'get_max_resource_size': helpers.get_max_resource_size,
            'nl_to_br': helpers.nl_to_br,
        }

    # IPackageController

    def before_index(self, pkg_dict):

        # Remove internal non-indexable fields

        # admin_notes
        pkg_dict.pop('admin_notes', None)
        pkg_dict.pop('extras_admin_notes', None)

        # sampling_procedure_notes
        pkg_dict.pop('sampling_procedure_notes', None)
        pkg_dict.pop('extras_sampling_procedure_notes', None)

        # response_rate_notes
        pkg_dict.pop('response_rate_notes', None)
        pkg_dict.pop('extras_response_rate_notes', None)

        # data_collection_notes
        pkg_dict.pop('data_collection_notes', None)
        pkg_dict.pop('extras_data_collection_notes', None)

        # weight_notes
        pkg_dict.pop('weight_notes', None)
        pkg_dict.pop('extras_weight_notes', None)

        # clean_ops_notes
        pkg_dict.pop('clean_ops_notes', None)
        pkg_dict.pop('extras_clean_ops_notes', None)

        # data_accs_notes
        pkg_dict.pop('data_accs_notes', None)
        pkg_dict.pop('extras_data_accs_notes', None)

        # Index labels on selected fields

        schema = scheming_get_dataset_schema('dataset')
        fields = ['data_collector', 'keywords', 'sampling_procedure',
                  'operational_purpose_of_data',  'data_collection_technique',
                  'process_status', 'identifiability']
        for field in fields:
            if pkg_dict.get(field):
                value = pkg_dict[field]

                # Free text values: value1,value2
                if field == 'data_collector':
                    pkg_dict['vocab_' + field] = helpers.normalize_list(value)

                # Select values: ["value1","value2"]
                else:
                    try:
                        values = json.loads(pkg_dict[field])
                    except ValueError:
                        values = [value]
                    out = []
                    for schema_field in schema['dataset_fields']:
                        if schema_field['field_name'] == field:
                            for item in values:
                                for choice in schema_field['choices']:
                                    if choice['value'] == item:
                                        out.append(choice['label'])
                    pkg_dict['vocab_' + field] = out

        # Index additional data for deposited dataset

        if pkg_dict.get('type') == 'deposited-dataset':
            # curator
            curator_id = pkg_dict.get('curator_id')
            if curator_id:
                try:
                    curator = toolkit.get_action('user_show')(
                        {'ignore_auth': True}, {'id': curator_id})
                    pkg_dict['curator_display_name'] = curator.get('display_name')
                except toolkit.ObjectNotFound:
                    pass
            # depositor
            depositor_id = pkg_dict.get('creator_user_id')
            if depositor_id:
                try:
                    depositor = toolkit.get_action('user_show')(
                        {'ignore_auth': True}, {'id': depositor_id})
                    pkg_dict['depositor_display_name'] = depositor.get('display_name')
                except toolkit.ObjectNotFound:
                    pass
            # data-container
            owner_org_dest_id = pkg_dict.get('owner_org_dest')
            if owner_org_dest_id:
                try:
                    owner_org_dest = toolkit.get_action('organization_show')(
                        {'ignore_auth': True}, {'id': owner_org_dest_id})
                    pkg_dict['owner_org_dest_display_name'] = owner_org_dest.get('display_name')
                except toolkit.ObjectNotFound:
                    pass

        return pkg_dict

    # Always include sub-containers to container_read search
    def before_search(self, search_params):
        if toolkit.c.controller == 'ckanext.unhcr.controllers.extended_organization:ExtendedOrganizationController':
            toolkit.c.include_children_selected = True

            # helper function
            def _children_name_list(children):
                name_list = []
                for child in children:
                    name = child.get('name', "")
                    name_list += [name] + _children_name_list(child.get('children', []))
                return name_list

            # update filter query
            children = _children_name_list(group_tree_section(toolkit.c.id, type_='data-container', include_parents=False, include_siblings=False).get('children',[]))
            if children:
                search_params['fq'] = 'organization:%s' % toolkit.c.id
                for name in children:
                    if name:
                        search_params['fq'] += ' OR organization:%s' %  name

        return search_params

    def after_create(self, context, data_dict):
        if not context.get('job'):
            if data_dict.get('state') == 'active':
                toolkit.enqueue_job(jobs.process_dataset_on_create, [data_dict['id']])

        if data_dict.get('type') == 'deposited-dataset':
            user_id = None
            if context.get('auth_user_obj'):
                user_id = context['auth_user_obj'].id
            elif context.get('user'):
                user = toolkit.get_action('user_show')(
                    {'ignore_auth': True}, {'id': context['user']})
                user_id = user['id']
            if user_id:
                helpers.create_curation_activity('dataset_deposited', data_dict['id'],
                    data_dict['name'], user_id)

    def after_delete(self, context, data_dict):
        if not context.get('job'):
            toolkit.enqueue_job(jobs.process_dataset_on_delete, [data_dict['id']])

    def after_update(self, context, data_dict):
        if not context.get('job'):
            if data_dict.get('state') == 'active':
                toolkit.enqueue_job(jobs.process_dataset_on_update, [data_dict['id']])

    # IAuthFunctions

    def get_auth_functions(self):
        functions = auth.restrict_access_to_get_auth_functions()
        functions['resource_download'] = auth.resource_download
        functions['unhcr_datastore_info'] = auth.unhcr_datastore_info
        functions['unhcr_datastore_search'] = auth.unhcr_datastore_search
        functions['unhcr_datastore_search_sql'] = auth.unhcr_datastore_search_sql
        functions['datasets_validation_report'] = auth.datasets_validation_report
        functions['organization_create'] = auth.organization_create
        functions['package_activity_list'] = auth.package_activity_list
        functions['package_create'] = auth.package_create
        functions['package_update'] = auth.package_update
        functions['dataset_collaborator_create'] = auth.dataset_collaborator_create
        functions['access_request_list_for_user'] = auth.access_request_list_for_user
        functions['access_request_create'] = auth.access_request_create
        functions['access_request_update'] = auth.access_request_update
        functions['user_update_sysadmin'] = auth.user_update_sysadmin
        functions['search_index_rebuild'] = auth.search_index_rebuild
        return functions

    # IActions

    def get_actions(self):
        return {
            'access_request_list_for_user': actions.access_request_list_for_user,
            'access_request_update': actions.access_request_update,
            'access_request_create': actions.access_request_create,
            'package_update': actions.package_update,
            'package_publish_microdata': actions.package_publish_microdata,
            'package_get_microdata_collections': actions.package_get_microdata_collections,
            'organization_create': actions.organization_create,
            'organization_member_create': actions.organization_member_create,
            'organization_member_delete': actions.organization_member_delete,
            'container_request_list': actions.container_request_list,
            'package_activity_list': actions.package_activity_list,
            'dashboard_activity_list': actions.dashboard_activity_list,
            'user_activity_list': actions.user_activity_list,
            'group_activity_list': actions.group_activity_list,
            'organization_activity_list': actions.organization_activity_list,
            'recently_changed_packages_activity_list': actions.recently_changed_packages_activity_list,
            'package_activity_list_html': actions.package_activity_list_html,
            'dashboard_activity_list_html': actions.dashboard_activity_list_html,
            'user_activity_list_html': actions.user_activity_list_html,
            'group_activity_list_html': actions.group_activity_list_html,
            'organization_activity_list_html': actions.organization_activity_list_html,
            'recently_changed_packages_activity_list_html': actions.recently_changed_packages_activity_list_html,
            'datasets_validation_report': actions.datasets_validation_report,
            'user_update_sysadmin': actions.user_update_sysadmin,
            'search_index_rebuild': actions.search_index_rebuild,
        }

    # IValidators

    def get_validators(self):
        return {
            'ignore_if_attachment': validators.ignore_if_attachment,
            'linked_datasets_validator': validators.linked_datasets,
            'unhcr_choices': validators.unhcr_choices,
            'deposited_dataset_owner_org': validators.deposited_dataset_owner_org,
            'deposited_dataset_owner_org_dest': validators.deposited_dataset_owner_org_dest,
            'deposited_dataset_curation_state': validators.deposited_dataset_curation_state,
            'deposited_dataset_curator_id': validators.deposited_dataset_curator_id,
            'always_false_if_not_sysadmin': validators.always_false_if_not_sysadmin,
            'visibility_validator': validators.visibility_validator,
            'file_type_validator': validators.file_type_validator,
            'upload_not_empty': validators.upload_not_empty,
            'object_id_validator': validators.object_id_validator,
            'activity_type_exists': validators.activity_type_exists,
            'owner_org_validator': validators.owner_org_validator,
        }

    # IPermissionLabels

    def get_dataset_labels(self, dataset_obj):
        # https://github.com/ckan/ckan/blob/master/ckanext/example_ipermissionlabels/plugin.py

        # For deposited datasets
        if dataset_obj.type == 'deposited-dataset':
            labels = [
                'deposited-dataset',
                'creator-%s' % dataset_obj.creator_user_id,
            ]

        # For normal datasets
        else:
            labels = super(UnhcrPlugin, self).get_dataset_labels(dataset_obj)

        return labels

    def get_user_dataset_labels(self, user_obj):
        # https://github.com/ckan/ckan/blob/master/ckanext/example_ipermissionlabels/plugin.py

        # For normal users
        # The label "creator-%s" is here for a package creator
        labels = super(UnhcrPlugin, self).get_user_dataset_labels(user_obj)

        # For curating users
        # Adding "deposited-dataset" label for data curators
        if user_obj:

            if user_obj.external:
                return ['']

            context = {u'user': user_obj.id}
            deposit = helpers.get_data_deposit()
            orgs = toolkit.get_action('organization_list_for_user')(context, {})
            for org in orgs:
                if deposit['id'] == org['id']:
                    labels.extend(['deposited-dataset'])

        return labels

    # IBlueprint

    def get_blueprint(self):
        return [
            blueprints.unhcr_access_requests_blueprint,
            blueprints.unhcr_admin_blueprint,
            blueprints.unhcr_data_container_blueprint,
            blueprints.unhcr_metrics_blueprint,
            blueprints.unhcr_search_index_blueprint,
            blueprints.unhcr_user_blueprint,
        ]
