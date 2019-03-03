import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
import ckan.logic.action.get as get_core
import ckan.logic.action.patch as patch_core
import ckan.logic.action.delete as delete_core
from ckanext.unhcr.mailer import mail_data_container_update_to_user
log = logging.getLogger(__name__)


class DataContainerController(toolkit.BaseController):

    def approve(self, id):

        # check access and state
        _raise_not_authz_or_not_pending(id)

        # organization_patch state=active
        org_dict = patch_core.organization_patch({}, {'id': id, 'state': 'active'})

        # send approval email
        mail_data_container_update_to_user({}, org_dict, event='approval')

        # show flash message and redirect
        toolkit.h.flash_success('Data container "{}" approved'.format(org_dict['title']))
        toolkit.redirect_to('data-container_read', id=id)

    def reject(self, id, *args, **kwargs):

        # check access and state
        _raise_not_authz_or_not_pending(id)

        # send rejection email
        org_dict = get_core.organization_show({'model': model}, {'id': id})
        mail_data_container_update_to_user({}, org_dict, event='rejection')

        # call organization_purge
        delete_core.organization_purge({'model': model}, {'id': id})

        # show flash message and redirect
        toolkit.h.flash_error('Data container "{}" rejected'.format(org_dict['title']))
        toolkit.redirect_to('data-container_index')


def _raise_not_authz_or_not_pending(id):

    # check auth with toolkit.check_access
    toolkit.check_access('sysadmin', {'model': model})

    # check org exists and it's pending with organization_show
    org_dict = toolkit.get_action('organization_show')({}, {'id': id})
    if org_dict.get('state') != 'approval_needed':
        raise toolkit.ObjectNotFound('Data container "{}" not found'.format(id))
