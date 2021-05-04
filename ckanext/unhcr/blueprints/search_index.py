# -*- coding: utf-8 -*-

from flask import Blueprint
import ckan.model as model
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr.utils import require_user


unhcr_search_index_blueprint = Blueprint(
    'unhcr_search_index',
    __name__,
    url_prefix=u'/ckan-admin/search_index'
)


@require_user
def index():
    try:
        toolkit.check_access('sysadmin', {'user': toolkit.c.user})
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Not authorized to manage search index')

    return toolkit.render('admin/search_index.html')


@require_user
def rebuild():
    try:
        errors = toolkit.get_action('search_index_rebuild')({'user': toolkit.c.user}, {})
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Not authorized to rebuild search index')

    if errors:
        toolkit.h.flash_error('Search Index rebuild completed with errors')
        return toolkit.render('admin/search_index.html', { 'errors': "\n".join(errors) })
    else:
        toolkit.h.flash_success('Search Index rebuild completed successfully')
        return toolkit.redirect_to('unhcr_search_index.index')


unhcr_search_index_blueprint.add_url_rule(
    rule=u'/',
    view_func=index,
    methods=['GET',],
    strict_slashes=False,
)

unhcr_search_index_blueprint.add_url_rule(
    rule=u'/rebuild',
    view_func=rebuild,
    methods=['POST',],
)
