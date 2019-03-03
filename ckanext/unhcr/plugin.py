import json
import logging

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.plugins import DefaultTranslation
from ckan.lib.plugins import DefaultPermissionLabels

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

        # deposited dataset
        controller = 'ckanext.unhcr.controllers.deposited_dataset:DepositedDatasetController'
        _map.connect('/deposited-dataset/{id}/approve', controller=controller, action='approve')
        _map.connect('/deposited-dataset/{id}/reject', controller=controller, action='reject')

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

    def organization_facets(self, facets_dict, organization_type,
                            package_type):
        return self._facets(facets_dict)

    # ITemplateHelpers

    def get_helpers(self):
        return {
            'render_tree': helpers.render_tree,
            'page_authorized': helpers.page_authorized,
            'get_linked_datasets_for_form': helpers.get_linked_datasets_for_form,
            'get_linked_datasets_for_display': helpers.get_linked_datasets_for_display,
            'get_data_container': helpers.get_data_container,
            'get_data_container_for_depositing': helpers.get_data_container_for_depositing,
            'get_dataset_validation_error_or_none': helpers.get_dataset_validation_error_or_none,
            'get_all_data_containers': helpers.get_all_data_containers,
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

        return pkg_dict

    def after_create(self, context, data_dict):
        if not context.get('job'):
            toolkit.enqueue_job(jobs.process_dataset_fields, [data_dict['id']])
            toolkit.enqueue_job(jobs.process_dataset_links_on_create, [data_dict['id']])

    def after_delete(self, context, data_dict):
        if not context.get('job'):
            toolkit.enqueue_job(jobs.process_dataset_links_on_delete, [data_dict['id']])

    def after_update(self, context, data_dict):
        if not context.get('job'):
            toolkit.enqueue_job(jobs.process_dataset_links_on_update, [data_dict['id']])
            toolkit.enqueue_job(jobs.process_dataset_fields, [data_dict['id']])

    # IAuthFunctions

    def get_auth_functions(self):

        return auth.restrict_access_to_get_auth_functions()

    # IActions

    def get_actions(self):
        return {
            'organization_create': actions.organization_create,
        }

    # IValidators

    def get_validators(self):
        return {
            'ignore_if_attachment': validators.ignore_if_attachment,
            'linked_datasets_validator': validators.linked_datasets,
            'unhcr_choices': validators.unhcr_choices,
            'deposited_dataset_owner_org': validators.deposited_dataset_owner_org,
            'deposited_dataset_owner_org_dest': validators.deposited_dataset_owner_org_dest,
        }

    def get_dataset_labels(self, dataset_obj):
        # https://github.com/ckan/ckan/blob/master/ckanext/example_ipermissionlabels/plugin.py

        # For deposited datasets
        if dataset_obj.type == 'deposited-dataset':
            log.debug(dataset_obj.owner_org)
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
            depo = helpers.get_data_container_for_depositing()
            orgs = toolkit.get_action('organization_list_for_user')(context, {})
            for org in orgs:
                if depo['id'] == org['id']:
                    labels.extend(['deposited-dataset'])

        return labels
