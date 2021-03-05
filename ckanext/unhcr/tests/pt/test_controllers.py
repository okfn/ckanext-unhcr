# -*- coding: utf-8 -*-

import mock
import pytest
from ckan.lib.helpers import url_for
from ckan.lib.search import index_for
import ckan.model as model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestDataContainerController(object):

    # Config

    def setup(self):
        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.user1 = core_factories.User(name='user1', id='user1')
        self.user2 = core_factories.User(name='user2', id='user2')
        self.user3 = core_factories.User(name='user3', id='user3')

        # Containers
        self.container1 = factories.DataContainer(
            name='container1',
            id='container1',
        )
        self.container2 = factories.DataContainer(
            name='container2',
            id='container2',
        )

    # Helpers

    def get_request(self, app, url, user=None, **kwargs):
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.get(url, extra_environ=env, **kwargs)
        self.update_containers()
        return resp

    def post_request(self, app, url, data, user=None, **kwargs):
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.post(url, data, extra_environ=env, **kwargs)
        self.update_containers()
        return resp

    def update_containers(self):
        self.container1 = core_helpers.call_action(
            'organization_show', {'user': 'sysadmin'}, id='container1')
        self.container2 = core_helpers.call_action(
            'organization_show', {'user': 'sysadmin'}, id='container2')

    # General

    def test_membership(self, app):
        resp = self.get_request(app, '/data-container/membership', user='sysadmin')
        assert 'Manage Membership' in resp.body

    def test_membership_no_access(self, app):
        resp = self.get_request(app, '/data-container/membership', user='user1', status=403)

    def test_membership_user(self, app):
        resp = self.get_request(app, '/data-container/membership?username=user1', user='sysadmin')
        assert 'Manage Membership' in resp.body
        assert 'Add Containers' in resp.body
        assert 'Current Containers' in resp.body

    # Add Containers

    def test_membership_add(self, app):
        data = {
            'username': 'user1',
            'contnames': 'container1',
            'role': 'editor',
        }
        resp = self.post_request(app, '/data-container/membership_add', data, user='sysadmin')
        default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })
        assert resp.status_int == 302
        assert len(self.container1['users']) == 2
        assert self.container1['users'][0]['name'] == default_user['name']
        assert self.container1['users'][0]['capacity'] == 'admin'
        assert self.container1['users'][1]['name'] == 'user1'
        assert self.container1['users'][1]['capacity'] == 'editor'

    def test_membership_add_multiple_containers(self, app):
        data = {
            'username': 'user1',
            'contnames': ['container1', 'container2'],
            'role': 'editor',
        }
        resp = self.post_request(app, '/data-container/membership_add', data, user='sysadmin')
        default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })
        assert resp.status_int == 302
        assert len(self.container1['users']) == 2
        assert self.container1['users'][0]['name'] == default_user['name']
        assert self.container1['users'][0]['capacity'] == 'admin'
        assert self.container1['users'][1]['name'] == 'user1'
        assert self.container1['users'][1]['capacity'] == 'editor'
        assert len(self.container2['users']) == 2
        assert self.container2['users'][0]['name'] == default_user['name']
        assert self.container2['users'][0]['capacity'] == 'admin'
        assert self.container2['users'][1]['name'] == 'user1'
        assert self.container2['users'][1]['capacity'] == 'editor'

    def test_membership_add_no_access(self, app):
        data = {
            'username': 'user1',
            'contnames': 'container1',
            'role': 'editor',
        }
        resp = self.post_request(app, '/data-container/membership_add', data, user='user3', status=403)

    # Remove Container

    def test_membership_remove(self, app):
        self.test_membership_add(app)
        url = '/data-container/membership_remove?username=user1&contname=container1'
        resp = self.get_request(app, url, user='sysadmin')
        default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })
        assert resp.status_int == 302
        assert len(self.container1['users']) == 1
        assert self.container1['users'][0]['name'] == default_user['name']
        assert self.container1['users'][0]['capacity'] == 'admin'

    def test_membership_remove_no_access(self, app):
        url = '/data-container/membership_remove?username=default_test&contname=container1'
        resp = self.get_request(app, url, user='user3', status=403)


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestUserRegister(object):

    def setup(self):
        self.sysadmin = core_factories.Sysadmin()
        self.container = factories.DataContainer()
        self.payload = {
            'name': 'externaluser',
            'fullname': 'New External User',
            'email': 'fred@externaluser.com',
            'password1': 'TestPassword1',
            'password2': 'TestPassword1',
            'message': 'I can haz access?',
            'focal_point': 'REACH',
            'container': self.container['id'],
        }

    def test_custom_fields(self, app):
        resp = app.get(url_for('user.register'))
        assert resp.status_int == 200
        assert (
            'Please describe the dataset(s) you would like to submit' in
            resp.body
        )
        assert (
            '<textarea id="field-message"' in
            resp.body
        )
        assert (
            'Please select the region where the data was collected' in
            resp.body
        )
        assert (
            '<select id="field-container"' in
            resp.body
        )

    def test_register_success(self, app):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = app.post(url_for('user.register'), self.payload)


        # we should have created a user object with pending state
        user = toolkit.get_action('user_show')(
            {'ignore_auth': True},
            {'id': 'externaluser'}
        )
        assert model.State.PENDING == user['state']

        # we should have created an access request for an admin to approve/reject
        assert (
            1 ==
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == user['id'],
                AccessRequest.user_id == user['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        # we should have sent an email to someone to approve/reject the account
        mock_mailer.assert_called_once()
        assert self.sysadmin['name'] == mock_mailer.call_args[0][1][0]
        assert (
            '[UNHCR RIDL] - Request for new user account' ==
            mock_mailer.call_args[0][1][1]
        )

        # 'success' page content
        assert resp.status_int == 200
        assert 'Partner Account Requested' in resp.body
        assert "We'll send an email with further instructions" in resp.body

    def test_register_empty_message(self, app):
        self.payload['message'] = ''
        resp = app.post(url_for('user.register'), self.payload)
        assert "&#39;message&#39; is required" in resp.body
        action = toolkit.get_action("user_show")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
                {'ignore_auth': True},
                {'id': 'externaluser'}
            )

    def test_register_empty_focal_point(self, app):
        self.payload['focal_point'] = ''
        resp = app.post(url_for('user.register'), self.payload)
        assert "A focal point must be specified" in resp.body
        action = toolkit.get_action("user_show")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
                {'ignore_auth': True},
                {'id': 'externaluser'}
            )

    def test_no_containers(self, app):
        self.payload['container'] = ''
        resp = app.post(url_for('user.register'), self.payload)
        assert "A region must be specified" in resp.body
        action = toolkit.get_action("user_show")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
                {'ignore_auth': True},
                {'id': 'externaluser'}
            )

    def test_internal_user(self, app):
        self.payload['email'] = 'fred@unhcr.org'
        resp = app.post(url_for('user.register'), self.payload)
        assert (
            "Users with an @unhcr.org email may not register for a partner account."
            in resp.body
        )
        action = toolkit.get_action("user_show")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
                {'ignore_auth': True},
                {'id': 'externaluser'}
            )

    def test_logged_in(self, app):
        user = core_factories.User()

        app.get(
            url_for('user.register'),
            extra_environ={'REMOTE_USER': user['name'].encode('ascii')},
            status=403
        )
        app.get(
            url_for('user.register'),
            extra_environ={'REMOTE_USER': self.sysadmin['name'].encode('ascii')},
            status=403
        )
        app.post(
            url_for('user.register'),
            self.payload,
            extra_environ={'REMOTE_USER': user['name'].encode('ascii')},
            status=403
        )
        app.post(
            url_for('user.register'),
            self.payload,
            extra_environ={'REMOTE_USER': self.sysadmin['name'].encode('ascii')},
            status=403
        )


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestMetricsController(object):

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


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
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
        app.post('/ckan-admin/search_index/rebuild', extra_environ=env, status=302)

        # now package_search will tell us there is 1 dataset
        packages = toolkit.get_action('package_search')(context, data_dict)
        assert 1 == packages['count']
