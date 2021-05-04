# -*- coding: utf-8 -*-

from flask import Blueprint
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr.utils import require_user


unhcr_admin_blueprint = Blueprint('unhcr_admin', __name__, url_prefix=u'/ckan-admin')


@require_user
def index():
    try:
        toolkit.check_access('sysadmin', {})
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Need to be system administrator to administer')

    context = {'user': toolkit.c.user}
    users = toolkit.get_action('user_list')(context, {})
    return toolkit.base.render('admin/index.html', {
        'sysadmins': [u for u in users if u['sysadmin']],
        'all_users': [u for u in users if not u['sysadmin']],
    })


unhcr_admin_blueprint.add_url_rule(
    rule=u'/',
    view_func=index,
    methods=['GET',],
    strict_slashes=False,
)
