# -*- coding: utf-8 -*-

from flask import Blueprint
import ckan.plugins.toolkit as toolkit


unhcr_user_blueprint = Blueprint('unhcr_user', __name__, url_prefix=u'/user')


def sysadmin():
    if (not hasattr(toolkit.c, "user") or not toolkit.c.user):
        return toolkit.abort(403, "Forbidden")

    id_ = toolkit.request.form.get('id')
    status = toolkit.asbool(toolkit.request.form.get('status'))

    try:
        context = {'user': toolkit.c.user}
        data_dict = {'id': id_, 'is_sysadmin': status}
        user = toolkit.get_action('user_update_sysadmin')(context, data_dict)
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Not authorized to promote user to sysadmin')
    except toolkit.ObjectNotFound:
        return toolkit.abort(404, 'User not found')

    if status:
        toolkit.h.flash_success('Promoted {} to sysadmin'.format(user['display_name']))
    else:
        toolkit.h.flash_success('Revoked sysadmin permission from {}'.format(user['display_name']))
    return toolkit.h.redirect_to('unhcr_admin.index')


unhcr_user_blueprint.add_url_rule(
    rule=u'/sysadmin',
    view_func=sysadmin,
    methods=['POST',],
)
