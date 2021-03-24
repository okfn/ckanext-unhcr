# -*- coding: utf-8 -*-

import mock
import pytest
from sqlalchemy import select, and_
from ckan.lib.helpers import url_for
from ckan.lib.search import index_for
import ckan.model as model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import factories, mocks


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestUserController(object):

    def test_sysadmin_not_authorized(self, app):
        user = core_factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.post('/user/sysadmin', {}, extra_environ=env, status=403)

    def test_sysadmin_invalid_user(self, app):
        user = core_factories.Sysadmin()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.post(
            '/user/sysadmin',
            {'id': 'fred', 'status': '1' },
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
            {'id': user['id'], 'status': '1' },
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
            {'id': user['id'], 'status': '0' },
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


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestAdminController(object):
    def test_index_sysadmin(self, app):
        user = core_factories.Sysadmin()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.get('/ckan-admin', extra_environ=env, status=200)

    def test_index_not_authorized(self, app):
        user = core_factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        app.get('/ckan-admin', extra_environ=env, status=403)


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestExtendedPackageController(object):

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
            users=[
                {'name': 'user1', 'capacity': 'admin'},
            ],
        )
        self.container2 = factories.DataContainer(
            name='container2',
            id='container2',
            users=[
                {'name': 'user2', 'capacity': 'admin'},
            ],
        )

        # Datasets
        self.dataset1 = factories.Dataset(
            name='dataset1',
            title='Test Dataset 1',
            owner_org='container1',
            data_collection_technique = 'f2f',
            sampling_procedure = 'nonprobability',
            operational_purpose_of_data = 'cartography',
            user=self.user1,
            visibility='private',
        )

        # Resources
        self.resource1 = factories.Resource(
            name='resource1',
            package_id='dataset1',
            url_type='upload',
            upload=mocks.FakeFileStorage(),
            url = "http://fakeurl/test.txt",
        )

    # Helpers

    def make_dataset_request(self, app, dataset_id=None, user=None, **kwargs):
        url = '/dataset/copy/%s' % dataset_id
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_resource_copy_request(self, app, dataset_id=None, resource_id=None, user=None, **kwargs):
        url = '/dataset/%s/resource_copy/%s' % (dataset_id, resource_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_resource_download_request(self, app, dataset_id, resource_id, user=None, **kwargs):
        url = toolkit.url_for(
            controller='package',
            action='resource_download',
            id=dataset_id,
            resource_id=resource_id
        )
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_request_access_request(self, app, dataset_id, user, message, **kwargs):
        url = '/dataset/{}/request_access'.format(dataset_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.post(
            url,
            {'message': message},
            extra_environ=env,
            **kwargs
        )
        return resp

    # Dataset

    def test_dataset_copy(self, app):
        resp = self.make_dataset_request(app, dataset_id='dataset1', user='user1')
        assert 'action="/dataset/new"' in resp.body
        assert 'You are copying' in resp.body
        assert 'f2f' in resp.body
        assert 'nonprobability' in resp.body
        assert 'cartography' in resp.body
        assert 'Add Data' in resp.body
        assert 'container1' in resp.body

    def test_dataset_copy_to_other_org(self, app):
        resp = self.make_dataset_request(app, dataset_id='dataset1', user='user2')
        assert 'action="/dataset/new"' in resp.body
        assert 'You are copying' in resp.body
        assert 'f2f' in resp.body
        assert 'nonprobability' in resp.body
        assert 'cartography' in resp.body
        assert 'Add Data' in resp.body
        assert 'container1' not in resp.body

    def test_dataset_copy_no_orgs(self, app):
        resp = self.make_dataset_request(app, dataset_id='dataset1', user='user3', status=403)

    def test_dataset_copy_bad_dataset(self, app):
        resp = self.make_dataset_request(app, dataset_id='bad', user='user1', status=404)

    # Resource Upload

    def test_edit_resource_works(self, app):
        url = toolkit.url_for(
            controller='package',
            action='resource_edit',
            id=self.dataset1['id'],
            resource_id=self.resource1['id']
        )
        env = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}

        # Mock a resource edit payload
        data = {
            'id': self.resource1['id'],
            'name': self.resource1['name'],
            'type': self.resource1['type'],
            'description': 'updated',
            'format': self.resource1['format'],
            'file_type': self.resource1['file_type'],
            'date_range_start': self.resource1['date_range_start'],
            'date_range_end': self.resource1['date_range_end'],
            'version': self.resource1['version'],
            'process_status': self.resource1['process_status'],
            'identifiability': self.resource1['identifiability'],

            'url': 'test.txt',
            'save': ''

        }

        resp = app.post(url, data, extra_environ=env)

        assert 'The form contains invalid entries:' not in resp.body

    def test_edit_resource_must_provide_upload(self, app):
        url = toolkit.url_for(
            controller='package',
            action='resource_edit',
            id=self.dataset1['id'],
            resource_id=self.resource1['id']
        )
        env = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}

        # Mock a resource edit payload
        data = {
            'id': self.resource1['id'],
            'name': self.resource1['name'],
            'type': self.resource1['type'],
            'description': 'updated',
            'format': self.resource1['format'],
            'file_type': self.resource1['file_type'],
            'date_range_start': self.resource1['date_range_start'],
            'date_range_end': self.resource1['date_range_end'],
            'version': self.resource1['version'],
            'process_status': self.resource1['process_status'],
            'identifiability': self.resource1['identifiability'],

            'url': '',
            'clear_upload': 'true',
            'save': ''

        }

        resp = app.post(url, data, extra_environ=env)

        assert 'The form contains invalid entries:' in resp.body
        assert 'All data resources require an uploaded file' in resp.body

    # Resource Copy

    def test_resource_copy(self, app):
        resp = self.make_resource_copy_request(
            app, dataset_id='dataset1', resource_id=self.resource1['id'], user='user1')
        assert 'action="/dataset/new_resource/dataset1"' in resp.body
        assert 'resource1 (copy)' in resp.body
        assert 'anonymized_public' in resp.body
        assert 'Add'in resp.body

    def test_resource_copy_no_access(self, app):
        resp = self.make_resource_copy_request(
            app, dataset_id='dataset1', resource_id=self.resource1['id'], user='user2',
            status=403
        )

    def test_resource_copy_bad_resource(self, app):
        resp = self.make_resource_copy_request(
            app, dataset_id='dataset1', resource_id='bad', user='user1',
            status=404
        )

    # Resource Download

    def test_resource_download_anonymous(self, app):
        resp = self.make_resource_download_request(
            app, dataset_id='dataset1', resource_id=self.resource1['id'], user=None,
            status=403
        )

    def test_resource_download_no_access(self, app):
        resp = self.make_resource_download_request(
            app, dataset_id='dataset1', resource_id=self.resource1['id'], user='user3',
            status=403
        )

    def test_resource_download_collaborator(self, app):
        core_helpers.call_action(
            'dataset_collaborator_create',
            id='dataset1',
            user_id='user3',
            capacity='member',
        )
        resp = self.make_resource_download_request(
            app, dataset_id='dataset1', resource_id=self.resource1['id'], user='user3',
            status=200
        )

    def test_resource_download_bad_resource(self, app):
        resp = self.make_resource_download_request(
            app, dataset_id='dataset1', resource_id='bad', user='user1',
            status=404
        )

    def test_resource_download_valid(self, app):
        sql = select([
            model.Activity
        ]).where(
            and_(
                model.Activity.activity_type == 'download resource',
                model.Activity.object_id == self.dataset1['id'],
                model.Activity.user_id == 'user1',
            )
        )

        # before we start, this user has never downloaded this resource before
        result = model.Session.execute(sql).fetchall()
        assert 0 == len(result)

        resp = self.make_resource_download_request(
            app, dataset_id='dataset1', resource_id=self.resource1['id'], user='user1',
            status=200
        )

        # after we've downloaded the resource, we should also
        # have also logged a 'download resource' action for this user/resource
        result = model.Session.execute(sql).fetchall()
        assert 1 == len(result)

    # Request Access

    def test_request_access_invalid_method(self, app):
        resp = app.get(
            '/dataset/dataset1/request_access',
            extra_environ={'REMOTE_USER': 'user3'},
            status=404
        )

    def test_request_access_missing_message(self, app):
        self.make_request_access_request(
            app, dataset_id='dataset1', user='user3', message='',
            status=400
        )

    def test_request_access_duplicate(self, app):
        rec = AccessRequest(
            user_id=self.user3['id'],
            object_id=self.dataset1['id'],
            object_type='package',
            message='I can haz access?',
            role='member',
        )
        model.Session.add(rec)
        model.Session.commit()
        resp = self.make_request_access_request(
            app, dataset_id='dataset1', user='user3', message='me again',
            status=400
        )

    def test_request_access_invalid_dataset(self, app):
        self.make_request_access_request(
            app, dataset_id='bad', user='user3', message='I can haz access?',
            status=404
        )

    def test_request_access_not_authorized(self, app):
        self.make_request_access_request(
            app, dataset_id='dataset1', user=None, message='I can haz access?',
            status=403
        )

    def test_request_access_valid(self, app):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                app, dataset_id='dataset1', user='user3', message='I can haz access?',
                status=302
            )

        mock_mailer.assert_called_once()
        assert 'user1' == mock_mailer.call_args[0][1][0]
        assert (
            '[UNHCR RIDL] - Request for access to dataset: "dataset1"' ==
            mock_mailer.call_args[0][1][1]
        )
        # call_args[0][1][2] is the HTML message body
        # but we're not going to make any assertions about it here
        # see the mailer tests for this

        assert (
            1 ==
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == self.dataset1['id'],
                AccessRequest.user_id == self.user3['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        resp2 = resp.follow(extra_environ={'REMOTE_USER': 'user3'}, status=200)
        assert (
            'Requested access to download resources from Test Dataset 1' in
            resp2.body
        )

    def test_request_access_user_already_has_access(self, app):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                app, dataset_id='dataset1', user='user1', message='I can haz access?',
                status=302
            )

        mock_mailer.assert_not_called()

        assert (
            0 ==
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == self.dataset1['id'],
                AccessRequest.user_id == self.user1['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        resp2 = resp.follow(extra_environ={'REMOTE_USER': 'user1'}, status=200)
        assert (
            'You already have access to download resources from Test Dataset 1' in
            resp2.body
        )


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
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
            {'message': message},
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


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
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
            owner_org=self.container1["id"], visibility="private"
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
        resp = app.post(url, data, extra_environ=env, **kwargs)
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
        resp = self.post_request(app, url, {}, user='sysadmin')
        default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })
        assert resp.status_int == 302
        assert len(self.container1['users']) == 1
        assert self.container1['users'][0]['name'] == default_user['name']
        assert self.container1['users'][0]['capacity'] == 'admin'

    def test_membership_remove_no_access(self, app):
        url = '/data-container/membership_remove?username=default_test&contname=container1'
        resp = self.post_request(app, url, {}, user='user3', status=403)


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


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestPrivateResources(object):

    def setup(self):
        # Users
        self.normal_user = core_factories.User()
        self.org_user = core_factories.User()
        self.sysadmin = core_factories.Sysadmin()

        # Containers
        factories.DataContainer(name='data-deposit', id='data-deposit')
        self.container = factories.DataContainer(
            users=[
                {'name': self.org_user['name'], 'capacity': 'member'}
            ]
        )

    def test_private_is_false_if_not_sysadmin(self):
        dataset = factories.Dataset(
            private=True, user=self.normal_user)

        assert dataset['private'] == False

    def test_private_can_be_true_if_sysadmin(self):
        dataset = factories.Dataset(
            private=True,
            visibility='private',
            user=self.sysadmin)

        assert dataset['private'] == True

    def test_access_visibility_public(self, app):

        dataset = factories.Dataset(
            visibility='public'
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )

        url = toolkit.url_for(
            controller='package',
            action='resource_download',
            id=dataset['id'],
            resource_id=resource['id'])

        # We don't have data but we pass authorization
        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=404)

    def test_access_visibility_restricted(self, app):

        dataset = factories.Dataset(
            visibility='restricted'
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )

        url = toolkit.url_for(
            controller='package',
            action='resource_download',
            id=dataset['id'],
            resource_id=resource['id'])

        # We don't pass authorization (forbidden)
        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=403)

    def test_access_visibility_restricted_pages_visible(self, app):

        dataset = factories.Dataset(
            visibility='restricted',
            owner_org=self.container['id'],
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )

        url = toolkit.url_for('dataset_read', id=dataset['id'])

        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)

        environ = {'REMOTE_USER': self.org_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)

        environ = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)

    def test_access_visibility_private(self, app):

        dataset = factories.Dataset(
            visibility='private',
            owner_org=self.container['id'],
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )

        url = toolkit.url_for(
            controller='package',
            action='resource_download',
            id=dataset['id'],
            resource_id=resource['id'])

        # We don't pass authorization (forbidden)
        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=403)

        # We don't have data but we pass authorization
        environ = {'REMOTE_USER': self.org_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=404)

        # We don't have data but we pass authorization
        environ = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=404)

    @pytest.mark.skip(reason="why is the private dataset still available in the test env?")
    def test_access_visibility_private_pages_not_visible(self, app):
        dataset = factories.Dataset(
            private=True,
            visibility='private',
            owner_org=self.container['id'],
            user=self.sysadmin,
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )

        url = toolkit.url_for('dataset_read', id=dataset['id'])

        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=404)

        environ = {'REMOTE_USER': self.org_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)

        environ = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)
