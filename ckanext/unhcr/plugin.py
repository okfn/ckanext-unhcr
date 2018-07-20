import logging
from ckan import model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.plugins import DefaultTranslation
from ckanext.unhcr import actions, auth, helpers, jobs, validators
log = logging.getLogger(__name__)


class UnhcrPlugin(plugins.SingletonPlugin, DefaultTranslation):
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

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'unhcr')

    # IRoutes

    def before_map(self, _map):
        controller = 'ckanext.unhcr.controllers:DataContainer'
        _map.connect('/data-container/{id}/approve',
                     controller=controller,
                     action='approve')
        _map.connect('/data-container/{id}/reject',
                     controller=controller,
                     action='reject')

        return _map

    # IFacets

    def _facets(self, facets_dict):
        if 'groups' in facets_dict:
            del facets_dict['groups']
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
        }
