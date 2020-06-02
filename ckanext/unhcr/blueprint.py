# -*- coding: utf-8 -*-

from flask import Blueprint
import ckan.plugins.toolkit as toolkit
from .helpers import user_is_curator
from .metrics import (
    get_datasets_by_date,
    get_datasets_by_downloads,
    get_containers,
    get_containers_by_date,
    get_tags,
    get_keywords,
    get_users_by_datasets,
    get_users_by_downloads,
)


unhcr_metrics_blueprint = Blueprint('unhcr_metrics', __name__)
unhcr_access_requests_blueprint = Blueprint('unhcr_access_requests', __name__)


# Metrics

def metrics():
    if (
        not hasattr(toolkit.c, "user") or
        not toolkit.c.user or
        not (toolkit.c.userobj.sysadmin or user_is_curator())
    ):
        return toolkit.abort(403, "Forbidden")

    context = { 'user': toolkit.c.user }

    return toolkit.render('metrics/index.html', {
        'metrics': [
            get_datasets_by_date(context),
            get_datasets_by_downloads(context),
            get_containers_by_date(context),
            get_containers(context),
            get_tags(context),
            get_keywords(context),
            get_users_by_datasets(context),
            get_users_by_downloads(context),
        ]
    })

unhcr_metrics_blueprint.add_url_rule(
    rule=u'/metrics',
    view_func=metrics,
    methods=['GET',]
)


# Access Requests

def access_requests_approve(request_id):
    if (not hasattr(toolkit.c, "user") or not toolkit.c.user):
        return toolkit.abort(403, "Forbidden")

    try:
        toolkit.get_action('access_request_update')(
            {'user': toolkit.c.user}, {'id': request_id, 'status': 'approved'}
        )
    except toolkit.ObjectNotFound as e:
        return toolkit.abort(404, toolkit._(str(e)))
    except toolkit.NotAuthorized:
        return toolkit.abort(403, toolkit._(u'Not Authorized to approve this request'))

    toolkit.h.flash_success('Access Request Approved')

    return toolkit.redirect_to('dashboard.requests')

def access_requests_reject(request_id):
    if (not hasattr(toolkit.c, "user") or not toolkit.c.user):
        return toolkit.abort(403, "Forbidden")

    try:
        toolkit.get_action('access_request_update')(
            {'user': toolkit.c.user}, {'id': request_id, 'status': 'rejected'}
        )
    except toolkit.ObjectNotFound as e:
        return toolkit.abort(404, toolkit._(str(e)))
    except toolkit.NotAuthorized:
        return toolkit.abort(403, toolkit._(u'Not Authorized to reject this request'))

    toolkit.h.flash_success('Access Request Rejected')

    return toolkit.redirect_to('dashboard.requests')


unhcr_access_requests_blueprint.add_url_rule(
    rule=u'/access-requests/approve/<request_id>',
    view_func=access_requests_approve,
    methods=['GET',]
)

unhcr_access_requests_blueprint.add_url_rule(
    rule=u'/access-requests/reject/<request_id>',
    view_func=access_requests_reject,
    methods=['GET',]
)
