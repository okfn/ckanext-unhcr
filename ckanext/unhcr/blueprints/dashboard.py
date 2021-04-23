# -*- coding: utf-8 -*-

import logging
from flask import Blueprint
from ckan import model
from ckan.views.user import _extra_template_variables
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr import helpers
from ckanext.unhcr.utils import require_user


log = logging.getLogger(__name__)


unhcr_dashboard_blueprint = Blueprint('unhcr_dashboard', __name__, url_prefix=u'/dashboard')


@require_user
def requests():
    if not helpers.user_is_container_admin() and not toolkit.c.userobj.sysadmin:
        return toolkit.abort(403, "Forbidden")

    context = {'model': model, 'user': toolkit.c.user}

    try:
        new_container_requests = toolkit.get_action('container_request_list')(
            context, {'all_fields': True}
        )
    except (toolkit.NotAuthorized, toolkit.ObjectNotFound):
        new_container_requests = []

    try:
        access_requests = toolkit.get_action('access_request_list_for_user')(
            context, {}
        )
    except (toolkit.NotAuthorized, toolkit.ObjectNotFound):
        access_requests = []

    container_access_requests = [
        req for req in access_requests if req['object_type'] == 'organization'
    ]
    dataset_access_requests = [
        req for req in access_requests if req['object_type'] == 'package'
    ]
    user_account_requests = [
        req for req in access_requests if req['object_type'] == 'user'
    ]

    context = {
        'model': model,
        'session': model.Session,
        'user': toolkit.c.user,
        'auth_user_obj': toolkit.c.userobj,
        'for_view': True,
    }

    template_vars = _extra_template_variables(
        context,
        {'id': toolkit.c.userobj.id, 'user_obj': toolkit.c.userobj, 'offset': 0}
    )
    template_vars['new_container_requests'] = new_container_requests
    template_vars['container_access_requests'] = container_access_requests
    template_vars['dataset_access_requests'] = dataset_access_requests
    template_vars['user_account_requests'] = user_account_requests

    return toolkit.render('user/dashboard_requests.html', template_vars)


unhcr_dashboard_blueprint.add_url_rule(
    u'/requests',
    view_func=requests
)
