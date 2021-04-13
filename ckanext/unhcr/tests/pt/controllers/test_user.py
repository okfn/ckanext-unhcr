# -*- coding: utf-8 -*-

import mock
import pytest
import ckan.model as model
from ckan.plugins import toolkit
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestUserController(object):

    def test_sysadmin_not_authorized(self, app):
        user = core_factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.post('/user/sysadmin', data={}, extra_environ=env, status=403)

    def test_sysadmin_invalid_user(self, app):
        user = core_factories.Sysadmin()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.post(
            '/user/sysadmin',
            data={'id': 'fred', 'status': '1' },
            extra_environ=env,
            status=404
        )

    def test_sysadmin_promote_success(self, app):
        admin = core_factories.Sysadmin()
        env = {'REMOTE_USER': admin['name'].encode('ascii')}

        # create a normal user
        user = core_factories.User(fullname='Alice')

        # promote them
        resp = app.post(
            '/user/sysadmin',
            data={'id': user['id'], 'status': '1' },
            extra_environ=env,
            status=302
        )
        resp2 = resp.follow(extra_environ=env, status=200)
        assert (
            'Promoted Alice to sysadmin' in
            resp2.body
        )

        # now they are a sysadmin
        userobj = model.User.get(user['id'])
        assert userobj.sysadmin

    def test_sysadmin_revoke_success(self, app):
        admin = core_factories.Sysadmin()
        env = {'REMOTE_USER': admin['name'].encode('ascii')}

        # create another sysadmin
        user = core_factories.Sysadmin(fullname='Bob')

        # revoke their status
        resp = app.post(
            '/user/sysadmin',
            data={'id': user['id'], 'status': '0' },
            extra_environ=env,
            status=302
        )
        resp2 = resp.follow(extra_environ=env, status=200)
        assert (
            'Revoked sysadmin permission from Bob' in
            resp2.body
        )

        # now they are not a sysadmin any more
        userobj = model.User.get(user['id'])
        assert not userobj.sysadmin


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
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
        resp = app.get(toolkit.url_for('user.register'))
        assert resp.status_code == 200
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
            resp = app.post(toolkit.url_for('user.register'), data=self.payload)


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
        assert resp.status_code == 200
        assert 'Partner Account Requested' in resp.body
        assert "We'll send an email with further instructions" in resp.body

    def test_register_empty_message(self, app):
        self.payload['message'] = ''
        resp = app.post(toolkit.url_for('user.register'), data=self.payload)
        assert "&#39;message&#39; is required" in resp.body
        action = toolkit.get_action("user_show")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
                {'ignore_auth': True},
                {'id': 'externaluser'}
            )

    def test_register_empty_focal_point(self, app):
        self.payload['focal_point'] = ''
        resp = app.post(toolkit.url_for('user.register'), data=self.payload)
        assert "A focal point must be specified" in resp.body
        action = toolkit.get_action("user_show")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
                {'ignore_auth': True},
                {'id': 'externaluser'}
            )

    def test_no_containers(self, app):
        self.payload['container'] = ''
        resp = app.post(toolkit.url_for('user.register'), data=self.payload)
        assert "A region must be specified" in resp.body
        action = toolkit.get_action("user_show")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
                {'ignore_auth': True},
                {'id': 'externaluser'}
            )

    def test_internal_user(self, app):
        self.payload['email'] = 'fred@unhcr.org'
        resp = app.post(toolkit.url_for('user.register'), data=self.payload)
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
            toolkit.url_for('user.register'),
            extra_environ={'REMOTE_USER': user['name'].encode('ascii')},
            status=403
        )
        app.get(
            toolkit.url_for('user.register'),
            extra_environ={'REMOTE_USER': self.sysadmin['name'].encode('ascii')},
            status=403
        )
        app.post(
            toolkit.url_for('user.register'),
            data=self.payload,
            extra_environ={'REMOTE_USER': user['name'].encode('ascii')},
            status=403
        )
        app.post(
            toolkit.url_for('user.register'),
            data=self.payload,
            extra_environ={'REMOTE_USER': self.sysadmin['name'].encode('ascii')},
            status=403
        )
