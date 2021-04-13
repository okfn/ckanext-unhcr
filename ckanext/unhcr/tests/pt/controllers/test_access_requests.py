# -*- coding: utf-8 -*-

import mock
import pytest
import ckan.model as model
from ckan.plugins import toolkit
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestAccessRequests(object):
    def setup(self):
        self.sysadmin = core_factories.Sysadmin()
        self.requesting_user = core_factories.User()
        self.standard_user = core_factories.User()
        self.pending_user = factories.ExternalUser(state=model.State.PENDING)

        self.container1_admin = core_factories.User()
        self.container1 = factories.DataContainer(
            users=[{"name": self.container1_admin["name"], "capacity": "admin"}]
        )
        self.container2 = factories.DataContainer()
        self.dataset1 = factories.Dataset(
            owner_org=self.container1["id"], visibility="restricted"
        )
        self.container1_request = AccessRequest(
            user_id=self.requesting_user["id"],
            object_id=self.container1["id"],
            object_type="organization",
            message="",
            role="member",
        )
        self.container2_request = AccessRequest(
            user_id=self.requesting_user["id"],
            object_id=self.container2["id"],
            object_type="organization",
            message="",
            role="member",
        )
        self.dataset_request = AccessRequest(
            user_id=self.requesting_user["id"],
            object_id=self.dataset1["id"],
            object_type="package",
            message="",
            role="member",
        )
        self.user_request_container1 = AccessRequest(
            user_id=self.pending_user["id"],
            object_id=self.pending_user["id"],
            object_type="user",
            message="",
            role="member",
            data={'default_containers': [self.container1["id"]]},
        )
        self.user_request_container2 = AccessRequest(
            user_id=self.pending_user["id"],
            object_id=self.pending_user["id"],
            object_type="user",
            message="",
            role="member",
            data={'default_containers': [self.container2["id"]]},
        )
        model.Session.add(self.container1_request)
        model.Session.add(self.container2_request)
        model.Session.add(self.dataset_request)
        model.Session.add(self.user_request_container1)
        model.Session.add(self.user_request_container2)
        model.Session.commit()

    def make_action_request(self, app, action, request_id, user=None, data=None, **kwargs):
        url = '/access-requests/{action}/{request_id}'.format(
            action=action, request_id=request_id
        )
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.post(url, data=data, extra_environ=env, **kwargs)
        return resp

    def make_list_request(self, app, user=None, **kwargs):
        url = '/dashboard/requests'
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def test_access_requests_reject_missing_param(self, app):
        self.make_action_request(
            app,
            action='reject',
            request_id=self.container1_request.id,
            user=self.container1_admin["name"],
            status=400,
            data={},
        )

    def test_access_requests_invalid_id(self, app):
        for action, data in [("approve", {}), ("reject", {'message': 'nope'})]:
            self.make_action_request(
                app,
                action=action,
                request_id='invalid-id',
                user=self.container1_admin["name"],
                status=404,
                data=data,
            )

    def test_access_requests_invalid_user(self, app):
        for action, data in [("approve", {}), ("reject", {'message': 'nope'})]:
            for user in [None, self.standard_user["name"]]:
                self.make_action_request(
                    app,
                    action=action,
                    request_id=self.container1_request.id,
                    user=user,
                    status=403,
                    data=data,
                )

    def test_access_requests_approve_container_admin(self, app):
        mock_mailer = mock.Mock()
        with mock.patch('ckanext.unhcr.mailer.mail_user_by_id', mock_mailer):
            resp = self.make_action_request(
                app,
                action='approve',
                request_id=self.container1_request.id,
                user=self.container1_admin["name"],
                status=302,
                data={},
            )
        mock_mailer.assert_called_once()
        # standard 'you've been added to a container' email
        assert (
            '[UNHCR RIDL] Membership: {}'.format(self.container1['title']) ==
            mock_mailer.call_args[0][1]
        )

        resp2 = resp.follow(
            extra_environ={'REMOTE_USER': self.container1_admin["name"].encode('ascii')},
            status=200
        )
        orgs = toolkit.get_action("organization_list_for_user")(
            {"user": self.requesting_user["name"]},
            {"id": self.requesting_user["name"], "permission": "read"}
        )
        assert self.container1['id'] == orgs[0]['id']
        assert 'approved' == self.container1_request.status
        assert 'Access Request Approved' in resp2.body

    def test_access_requests_reject_container_admin(self, app):
        mock_mailer = mock.Mock()
        with mock.patch('ckanext.unhcr.mailer.mail_user_by_id', mock_mailer):
            resp = self.make_action_request(
                app,
                action='reject',
                request_id=self.container1_request.id,
                user=self.container1_admin["name"],
                status=302,
                data={'message': 'nope'},
            )
        mock_mailer.assert_called_once()
        # your request has been rejected email
        assert (
            '[UNHCR RIDL] - Request for access to: "{}"'.format(self.container1['name']) ==
            mock_mailer.call_args[0][1]
        )

        resp2 = resp.follow(
            extra_environ={'REMOTE_USER': self.container1_admin["name"].encode('ascii')},
            status=200
        )
        orgs = toolkit.get_action("organization_list_for_user")(
            {"user": self.requesting_user["name"]},
            {"id": self.requesting_user["name"], "permission": "read"}
        )
        assert 0 == len(orgs)
        assert 'rejected' == self.container1_request.status
        assert 'Access Request Rejected' in resp2.body

    def test_access_requests_list_invalid_user(self, app):
        for user in [None, self.standard_user["name"]]:
            self.make_list_request(app, user=user, status=403)

    def test_access_requests_list_sysadmin(self, app):
        resp = self.make_list_request(app, user=self.sysadmin['name'], status=200)
        # sysadmin can see all the requests
        assert (
            '/access-requests/approve/{}'.format(self.container1_request.id)
            in resp.body
        )
        assert (
            '/access-requests/approve/{}'.format(self.container2_request.id)
            in resp.body
        )
        assert (
            '/access-requests/approve/{}'.format(self.dataset_request.id)
            in resp.body
        )
        assert (
            '/access-requests/approve/{}'.format(self.user_request_container1.id)
            in resp.body
        )
        assert (
            '/access-requests/approve/{}'.format(self.user_request_container2.id)
            in resp.body
        )

    def test_access_requests_list_container_admin(self, app):
        resp = self.make_list_request(app, user=self.container1_admin['name'], status=200)
        assert (
            '/access-requests/approve/{}'.format(self.container1_request.id)
            in resp.body
        )
        assert (
            '/access-requests/approve/{}'.format(self.dataset_request.id)
            in resp.body
        )
        assert (
            '/access-requests/approve/{}'.format(self.user_request_container1.id)
            in resp.body
        )
        # container1_admin can't see the requests for container2
        assert (
            '/access-requests/approve/{}'.format(self.container2_request.id)
            not in resp.body
        )
        assert (
            '/access-requests/approve/{}'.format(self.user_request_container2.id)
            not in resp.body
        )
