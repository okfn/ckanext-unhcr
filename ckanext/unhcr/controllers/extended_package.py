# -*- coding: utf-8 -*-

import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckan.controllers.package import PackageController
log = logging.getLogger(__name__)


class ExtendedPackageController(PackageController):

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
