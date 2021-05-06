# -*- coding: utf-8 -*-

import pytest
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestMetricsView(object):

    # Helpers

    def get_request(self, app, url, user=None, **kwargs):
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.get(url, extra_environ=env, **kwargs)
        return resp

    # Tests

    def test_metrics_not_logged_in(self, app):
        resp = self.get_request(app, '/metrics', status=403)

    def test_metrics_standard_user(self, app):
        user1 = core_factories.User(name='user1', id='user1')
        resp = self.get_request(app, '/metrics', user='user1', status=403)
        assert '<a href="/metrics">' not in resp.body

    def test_metrics_sysadmin(self, app):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        resp = self.get_request(app, '/metrics', user='sysadmin', status=200)

    def test_metrics_curator(self, app):
        curator = core_factories.User(name='curator', id='curator')
        deposit = factories.DataContainer(
            users=[
                {'name': 'curator', 'capacity': 'editor'},
            ],
            name='data-deposit',
            id='data-deposit'
        )
        resp = self.get_request(app, '/metrics', user='curator', status=200)