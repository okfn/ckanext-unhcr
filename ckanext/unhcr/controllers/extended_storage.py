from ckan import model
import ckan.plugins.toolkit as toolkit
from ckanext.cloudstorage.controller import StorageController
from ckanext.unhcr.activity import log_download_activity


class ExtendedStorageController(StorageController):

    def resource_download(self, id, resource_id, filename=None):
        """
        Wraps default `resource_download` endpoint checking
        the custom `resource_download` auth function
        """
        context = {'model': model, 'session': model.Session,
                   'user': toolkit.c.user, 'auth_user_obj': toolkit.c.userobj}

        # Check resource_download access
        try:
            toolkit.check_access(u'resource_download', context, {u'id': resource_id})
        except toolkit.ObjectNotFound:
            return toolkit.abort(404, toolkit._(u'Resource not found'))
        except toolkit.NotAuthorized:
            return toolkit.abort(403, toolkit._(u'Not Authorized to download the resource'))

        """
        ckanext.cloudstorage.controller.StorageController
        will issue a redirect to a file on S3
        so we log the download activity first. See notes at
        https://github.com/okfn/ckanext-unhcr/pull/289#issuecomment-624084628
        """
        log_download_activity(context, resource_id)
        return super(ExtendedStorageController, self).resource_download(
            id, resource_id, filename=filename
        )
