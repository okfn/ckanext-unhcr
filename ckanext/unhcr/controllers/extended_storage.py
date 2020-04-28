import os
from ckan import model
from ckan.common import config
import ckan.plugins.toolkit as toolkit


def get_base_controller():
    """
    if we're using ckanext-cloudstorage we want to extend
    ckanext.cloudstorage.controller:StorageController
    otherwise, we want to extend
    ckanext.unhcr.controllers.extended_package:ExtendedPackageController
    """

    if 'cloudstorage' in config['ckan.plugins']:
        from ckanext.cloudstorage.controller import StorageController
        return StorageController

    from ckanext.unhcr.controllers.extended_package import ExtendedPackageController
    return ExtendedPackageController


BaseController = get_base_controller()


class ExtendedStorageController(BaseController):
    def _log_download_activity(self, context, resource_id):
        """Log a resource download activity in the activity stream
        """
        user = context['user']
        user_id = None
        user_by_name = model.User.by_name(user.decode('utf8'))
        if user_by_name is not None:
            user_id = user_by_name.id

        activity_dict = {
            'activity_type': 'download resource',
            'user_id': user_id,
            'object_id': resource_id,
            'data': {}
        }

        activity_create_context = {
            'model': model,
            'user': user_id or user,
            'defer_commit': False,
            'ignore_auth': True,
        }

        create_activity = toolkit.get_action('activity_create')
        create_activity(activity_create_context, activity_dict)

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


        if 'ExtendedPackageController' in [b.__name__ for b in self.__class__.__bases__]:
            resp = super(ExtendedStorageController, self).resource_download(
                id, resource_id, filename=filename
            )
            self._log_download_activity(context, resource_id)
            return resp

        """
        ckanext.cloudstorage.controller.StorageController
        will issue a redirect to a file on S3
        so we log the download activity first. See notes at
        https://github.com/okfn/ckanext-unhcr/pull/289#issuecomment-624084628
        """
        self._log_download_activity(context, resource_id)
        return super(ExtendedStorageController, self).resource_download(
            id, resource_id, filename=filename
        )
