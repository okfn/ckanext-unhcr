# -*- coding: utf-8 -*-

from flask import Blueprint
from .metrics import metrics

unhcr_metrics_blueprint = Blueprint('unhcr_metrics', __name__)

unhcr_metrics_blueprint.add_url_rule(
    rule=u'/metrics',
    view_func=metrics,
    methods=['GET',]
)
