# encoding: utf-8
import json
import logging

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.plugins import DefaultTranslation
from ckan.lib.plugins import DefaultPermissionLabels

# 🙈
from ckan.lib.activity_streams import activity_stream_string_functions

from ckanext.unhcr import actions, auth, helpers, jobs, validators

from ckanext.scheming.helpers import scheming_get_dataset_schema

log = logging.getLogger(__name__)

_ = toolkit._


class UnhcrPlugin(plugins.SingletonPlugin, DefaultTranslation, DefaultPermissionLabels):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITranslation)
    plugins.implements(plugins.IFacets)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.IRoutes, inherit=True)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.IPermissionLabels)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'unhcr')

        activity_stream_string_functions['changed package'] = helpers.custom_activity_renderer

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
        _map.connect('deposited-dataset_curation_activity', '/deposited-dataset/curation_activity/{dataset_id}', controller=controller, action='activity')
        _map.connect('dataset_curation_activity','/dataset/curation_activity/{dataset_id}', controller=controller, action='activity')

        # package
        controller = 'ckanext.unhcr.controllers.extended_package:ExtendedPackageController'
        _map.connect('/dataset/copy/{id}', controller=controller, action='copy')
        _map.connect('/dataset/{id}/resource_copy/{resource_id}', controller=controller, action='resource_copy')

        # user
        controller = 'ckanext.unhcr.controllers.extended_user:ExtendedUserController'
        _map.connect('user_dashboard_requests', '/dashboard/requests', controller=controller, action='list_requests', ckan_icon='spinner')

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
            # General
            'get_data_container': helpers.get_data_container,
            'get_all_data_containers': helpers.get_all_data_containers,
            'get_dataset_count': helpers.get_dataset_count,
            # Hierarchy
            'get_allowable_parent_groups': helpers.get_allowable_parent_groups,
            'render_tree': helpers.render_tree,
            # Access restriction
            'page_authorized': helpers.page_authorized,
            # Lined datasets
            'get_linked_datasets_for_form': helpers.get_linked_datasets_for_form,
            'get_linked_datasets_for_display': helpers.get_linked_datasets_for_display,
            # Pending requests
            'get_pending_requests': helpers.get_pending_requests,
            # Deposited datasets
            'get_data_deposit': helpers.get_data_deposit,
            'get_data_curation_users': helpers.get_data_curation_users,
            'get_deposited_dataset_user_curation_status': helpers.get_deposited_dataset_user_curation_status,
            'get_deposited_dataset_user_curation_role': helpers.get_deposited_dataset_user_curation_role,
            'get_dataset_validation_report': helpers.get_dataset_validation_report,
            'get_user_deposited_drafts': helpers.get_user_deposited_drafts,
            # Misc
            'current_path': helpers.current_path,
            'get_field_label': helpers.get_field_label,
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

    def after_create(self, context, data_dict):
        if not context.get('job'):
            toolkit.enqueue_job(jobs.process_dataset_fields, [data_dict['id']])
            toolkit.enqueue_job(jobs.process_dataset_links_on_create, [data_dict['id']])

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
            toolkit.enqueue_job(jobs.process_dataset_links_on_delete, [data_dict['id']])

    def after_update(self, context, data_dict):
        if not context.get('job'):
            toolkit.enqueue_job(jobs.process_dataset_links_on_update, [data_dict['id']])
            toolkit.enqueue_job(jobs.process_dataset_fields, [data_dict['id']])

    # IAuthFunctions

    def get_auth_functions(self):
        functions = auth.restrict_access_to_get_auth_functions()
        functions['resource_download'] = auth.resource_download
        return functions

    # IActions

    def get_actions(self):
        return {
            'package_create': actions.package_create,
            'organization_create': actions.organization_create,
            'pending_requests_list': actions.pending_requests_list,
            'package_activity_list': actions.package_activity_list,
            'dashboard_activity_list': actions.dashboard_activity_list,
            'group_activity_list': actions.group_activity_list,
            'organization_activity_list': actions.organization_activity_list,
            'recently_changed_packages_activity_list': actions.recently_changed_packages_activity_list,
            'package_activity_list_html': actions.package_activity_list_html,
            'dashboard_activity_list_html': actions.dashboard_activity_list_html,
            'group_activity_list_html': actions.group_activity_list_html,
            'organization_activity_list_html': actions.organization_activity_list_html,
            'recently_changed_packages_activity_list_html': actions.recently_changed_packages_activity_list_html,
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
        }

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
            context = {u'user': user_obj.id}
            deposit = helpers.get_data_deposit()
            orgs = toolkit.get_action('organization_list_for_user')(context, {})
            for org in orgs:
                if deposit['id'] == org['id']:
                    labels.extend(['deposited-dataset'])

        return labels
