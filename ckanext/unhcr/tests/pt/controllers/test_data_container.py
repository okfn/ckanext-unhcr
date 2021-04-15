# -*- coding: utf-8 -*-

import mock
import pytest
import ckan.model as model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestDataContainerAccessRequests(object):

    def setup(self):
        self.deposit = factories.DataContainer(
            name='data-deposit',
            id='data-deposit',
        )
        self.user = core_factories.User(name='user1')
        self.admin = core_factories.User(name='admin')
        self.container = factories.DataContainer(
            name='container1',
            title='Test Container',
            users=[
                {'name': self.admin['name'], 'capacity': 'admin'},
            ]
        )

    def make_request_access_request(self, app, container_id, user, message, **kwargs):
        url = '/data-container/{}/request_access'.format(container_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.post(
            url,
            data={'message': message},
            extra_environ=env,
            **kwargs
        )
        return resp

    # Request Access

    def test_request_access_invalid_method(self, app):
        resp = app.get(
            '/data-container/container1/request_access',
            extra_environ={'REMOTE_USER': 'user1'},
            status=404
        )

    def test_request_access_missing_message(self, app):
        self.make_request_access_request(
            app, container_id='container1', user='user1', message='',
            status=400
        )

    def test_request_access_duplicate(self, app):
        rec = AccessRequest(
            user_id=self.user['id'],
            object_id=self.container['id'],
            object_type='organization',
            message='I can haz access?',
            role='member',
        )
        model.Session.add(rec)
        model.Session.commit()
        resp = self.make_request_access_request(
            app, container_id='container1', user='user1', message='me again',
            status=400
        )

    def test_request_access_invalid_containers(self, app):
        # this container doesn't exist
        self.make_request_access_request(
            app, container_id='bad', user='user1', message='I can haz access?',
            status=404
        )

        # we can't request access to the data-deposit
        # because it is _special and different_
        self.make_request_access_request(
            app, container_id='data-deposit', user='user3', message='I can haz access?',
            status=403
        )

    def test_request_access_not_authorized(self, app):
        self.make_request_access_request(
            app, container_id='container1', user=None, message='I can haz access?',
            status=403
        )

    def test_request_access_valid(self, app):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                app, container_id='container1', user='user1', message='I can haz access?',
                status=302
            )

        mock_mailer.assert_called_once()
        assert 'admin' == mock_mailer.call_args[0][1][0]
        assert (
            '[UNHCR RIDL] - Request for access to container: "Test Container"' ==
            mock_mailer.call_args[0][1][1]
        )
        # call_args[0][1][2] is the HTML message body
        # but we're not going to make any assertions about it here
        # see the mailer tests for this

        assert(
            1 ==
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == self.container['id'],
                AccessRequest.user_id == self.user['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        resp2 = resp.follow(extra_environ={'REMOTE_USER': 'user1'}, status=200)
        assert (
            'Requested access to container Test Container' in
            resp2.body
        )

    def test_request_access_user_already_has_access(self, app):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                app, container_id='container1', user='admin', message='I can haz access?',
                status=302
            )

        mock_mailer.assert_not_called()

        assert (
            0 ==
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == self.container['id'],
                AccessRequest.user_id == self.admin['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        resp2 = resp.follow(extra_environ={'REMOTE_USER': 'admin'}, status=200)
        assert (
            'You are already a member of Test Container' in
            resp2.body
        )


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate', 'with_request_context')
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
        resp = app.post(url, data=data, extra_environ=env, **kwargs)
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
        resp = self.post_request(app, '/data-container/membership_add', data, user='sysadmin', status=200)
        default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })
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
        resp = self.post_request(app, '/data-container/membership_add', data, user='sysadmin', status=200)
        default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })
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
        resp = self.post_request(app, url, {}, user='sysadmin', status=200)
        default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })
        assert len(self.container1['users']) == 1
        assert self.container1['users'][0]['name'] == default_user['name']
        assert self.container1['users'][0]['capacity'] == 'admin'

    def test_membership_remove_no_access(self, app):
        url = '/data-container/membership_remove?username=default_test&contname=container1'
        resp = self.post_request(app, url, {}, user='user3', status=403)
