# -*- coding: utf-8 -*-

from flask import Blueprint
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr.helpers import user_is_curator
from ckanext.unhcr.metrics import (
    get_datasets_by_date,
    get_datasets_by_downloads,
    get_containers,
    get_containers_by_date,
    get_tags,
    get_keywords,
    get_users_by_datasets,
    get_users_by_downloads,
)
from ckanext.unhcr.utils import require_user


unhcr_metrics_blueprint = Blueprint(
    'unhcr_metrics',
    __name__,
    url_prefix=u'/metrics'
)


@require_user
def metrics():
    if (not (toolkit.c.userobj.sysadmin or user_is_curator())):
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
    rule=u'/',
    view_func=metrics,
    methods=['GET',],
    strict_slashes=False,
)
