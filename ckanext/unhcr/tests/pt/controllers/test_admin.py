# -*- coding: utf-8 -*-

import pytest
from ckan.lib.search import index_for
import ckan.model as model
from ckan.plugins import toolkit
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestAdminController(object):

    def test_index_sysadmin(self, app):
        user = core_factories.Sysadmin()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.get('/ckan-admin', extra_environ=env, status=200)

    def test_index_not_authorized(self, app):
        user = core_factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.get('/ckan-admin', extra_environ=env, status=403)


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate', 'with_request_context')
class TestSearchIndexController(object):

    def test_search_index_not_admin(self, app):
        user = core_factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.get('/ckan-admin/search_index', extra_environ=env, status=403)

    def test_search_index_sysadmin(self, app):
        user = core_factories.Sysadmin()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.get('/ckan-admin/search_index', extra_environ=env, status=200)

    def test_search_index_rebuild_not_admin(self, app):
        user = core_factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.post('/ckan-admin/search_index/rebuild', extra_environ=env, status=403)

    def test_search_index_rebuild_sysadmin(self, app):
        user = core_factories.Sysadmin()
        data_dict = { 'q': '*:*', 'rows': 0,}
        context = { 'ignore_auth': True }

        # create a dataset
        factories.Dataset()
        package_index = index_for(model.Package)
        # clear the index
        package_index.clear()
        # package_search tell us there are 0 datasets
        packages = toolkit.get_action('package_search')(context, data_dict)
        assert 0 == packages['count']

        # invoke a search_index_rebuild
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.post('/ckan-admin/search_index/rebuild', extra_environ=env, status=200)

        # now package_search will tell us there is 1 dataset
        packages = toolkit.get_action('package_search')(context, data_dict)
        assert 1 == packages['count']
