# -*- coding: utf-8 -*-

from flask import Blueprint
import ckan.logic as logic
import ckan.model as model
import ckan.plugins.toolkit as toolkit
from ckan.lib.search import index_for, commit


unhcr_search_index_blueprint = Blueprint(
    'unhcr_search_index',
    __name__,
    url_prefix=u'/ckan-admin/search_index'
)


def index():
    if (not hasattr(toolkit.c, "user") or not toolkit.c.user):
        return toolkit.abort(403, "Forbidden")

    try:
        toolkit.check_access('sysadmin', {'user': toolkit.c.user})
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Not authorized to manage search index')

    return toolkit.render('admin/search_index.html')


def rebuild():
    if (not hasattr(toolkit.c, "user") or not toolkit.c.user):
        return toolkit.abort(403, "Forbidden")

    try:
        toolkit.check_access('sysadmin', {'user': toolkit.c.user})
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Not authorized to rebuild search index')

    package_ids = [
        r[0]
        for r in model.Session.query(model.Package.id)
        .filter(model.Package.state != "deleted")
        .all()
    ]
    package_index = index_for(model.Package)
    package_index.clear()
    errors = []
    context = {'model': model, 'ignore_auth': True, 'validate': False, 'use_cache': False}
    for pkg_id in package_ids:
        try:
            package_index.update_dict(
                logic.get_action('package_show')(context, {'id': pkg_id}),
                defer_commit=True
            )
        except Exception as e:
            errors.append('Encountered {error} processing {pkg}'.format(
                error=repr(e),
                pkg=pkg_id
            ))

    commit()
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
