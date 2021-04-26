# -*- coding: utf-8 -*-

import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckan.controllers.package import PackageController
from ckanext.scheming.helpers import scheming_get_dataset_schema
from ckanext.unhcr import mailer
from ckanext.unhcr.activity import log_download_activity
from ckanext.unhcr.utils import resource_is_blocked
log = logging.getLogger(__name__)


class ExtendedPackageController(PackageController):

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

        if resource_is_blocked(context, resource_id):
            return toolkit.abort(404, toolkit._(u'Resource not found'))

        resp = super(ExtendedPackageController, self).resource_download(
            id, resource_id, filename=filename
        )
        log_download_activity(context, resource_id)
        return resp

    # Activity

    def activity(self, dataset_id):
        '''Render package's internal activity stream page.'''

        context = {'model': model, 'user': toolkit.c.user}
        data_dict = {'id': dataset_id}
        try:
            # We check for package_show because
            # in some states package_update can be forbidden
            toolkit.check_access('package_show', context, data_dict)
            toolkit.c.pkg_dict = toolkit.get_action('package_show')(context, data_dict)
            toolkit.c.pkg = context['package']
            toolkit.c.package_activity_stream = toolkit.get_action(
                'package_activity_list_html')(
                context, {
                    'id': dataset_id,
                    'get_internal_activities': True
                })
        except toolkit.ObjectNotFound:
            toolkit.abort(404, toolkit._('Dataset not found'))
        except toolkit.NotAuthorized:
            toolkit.abort(403, toolkit._('Unauthorized to read the internal activity for dataset %s') % dataset_id)

        return toolkit.render('package/activity.html', {'dataset_type': 'deposited-dataset'})
