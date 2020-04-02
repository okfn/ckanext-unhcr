# -*- coding: utf-8 -*-

from flask import Blueprint
import ckan.plugins.toolkit as toolkit
from .helpers import user_is_curator
from .metrics import (
    get_datasets_by_date,
    get_containers,
    get_containers_by_date,
    get_tags,
    get_users,
)

def metrics():
    context = { 'user': toolkit.c.user }

    if not (toolkit.c.userobj.sysadmin or user_is_curator()):
        return toolkit.abort(403, 'Forbidden')

    return toolkit.render('metrics/index.html', {
        'metrics': [
            get_datasets_by_date(context),
            get_containers(context),
            get_containers_by_date(context),
            get_tags(context),
            get_users(context),
        ]
    })

unhcr_metrics_blueprint = Blueprint('unhcr_metrics', __name__)

unhcr_metrics_blueprint.add_url_rule(
    rule=u'/metrics',
    view_func=metrics,
    methods=['GET',]
)
