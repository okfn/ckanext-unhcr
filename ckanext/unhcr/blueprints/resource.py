# -*- coding: utf-8 -*-

import logging
from flask import Blueprint
from ckan import model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.views.resource import download as base_local_resource_download
from ckanext.s3filestore.views.resource import resource_download as base_s3_resource_download
from ckanext.unhcr.activity import log_download_activity
from ckanext.unhcr.utils import require_user, resource_is_blocked
log = logging.getLogger(__name__)


unhcr_resource_blueprint = Blueprint(
    u'unhcr_resource',
    __name__,
    url_defaults={u'package_type': u'dataset'}
)


@require_user
def resource_download(package_type, id, resource_id, filename=None):
    context = {'model': model, 'session': model.Session,
                'user': toolkit.c.user, 'auth_user_obj': toolkit.c.userobj}

    # Check resource_download access
    try:
        toolkit.check_access(u'resource_download', context.copy(), {u'id': resource_id})
    except toolkit.ObjectNotFound:
        return toolkit.abort(404, toolkit._(u'Resource not found'))
    except toolkit.NotAuthorized:
        return toolkit.abort(403, toolkit._(u'Not Authorized to download the resource'))

    if resource_is_blocked(context.copy(), resource_id):
        return toolkit.abort(404, toolkit._(u'Resource not found'))

    if plugins.plugin_loaded('s3filestore'):
        resp = base_s3_resource_download(package_type, id, resource_id, filename)
    else:
        resp = base_local_resource_download(package_type, id, resource_id, filename)

    log_download_activity(context.copy(), resource_id)
    return resp


unhcr_resource_blueprint.add_url_rule(
    u'/dataset/<id>/resource/<resource_id>/download',
    view_func=resource_download
)
unhcr_resource_blueprint.add_url_rule(
    u'/dataset/<id>/resource/<resource_id>/download/<filename>',
    view_func=resource_download
)
