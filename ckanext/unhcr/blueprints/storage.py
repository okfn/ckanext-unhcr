import logging
from flask import Blueprint
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckanext.s3filestore.views.resource import resource_download as base_resource_download
from ckanext.unhcr.activity import log_download_activity
from ckanext.unhcr.utils import require_user, resource_is_blocked
log = logging.getLogger(__name__)


unhcr_s3_resource_blueprint = Blueprint(
    u'unhcr_s3_resource',
    __name__,
    url_defaults={u'package_type': u'dataset'}
)


@require_user
def resource_download(package_type, id, resource_id, filename=None):
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

    """
    base_resource_download
    will issue a redirect to a file on S3
    so we log the download activity first. See notes at
    https://github.com/okfn/ckanext-unhcr/pull/289#issuecomment-624084628
    """
    log_download_activity(context, resource_id)
    return base_resource_download(package_type, id, resource_id, filename)


unhcr_s3_resource_blueprint.add_url_rule(
    u'/dataset/<id>/resource/<resource_id>/download',
    view_func=resource_download
)
unhcr_s3_resource_blueprint.add_url_rule(
    u'/dataset/<id>/resource/<resource_id>/download/<filename>',
    view_func=resource_download
)
unhcr_s3_resource_blueprint.add_url_rule(
    u'/deposited-dataset/<id>/resource/<resource_id>/download',
    view_func=resource_download
)
unhcr_s3_resource_blueprint.add_url_rule(
    u'/deposited-dataset/<id>/resource/<resource_id>/download/<filename>',
    view_func=resource_download
)
