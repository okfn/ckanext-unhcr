# -*- coding: utf-8 -*-

import mock
import pytest
from sqlalchemy import select, and_
import ckan.model as model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import factories, mocks


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate', 'with_request_context')
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
            visibility='restricted',
        )

        # Resources
        self.resource1 = factories.Resource(
            name='resource1',
            package_id='dataset1',
            url_type='upload',
            upload=mocks.FakeFileStorage(),
        )

    # Helpers

    def make_dataset_copy_request(self, app, dataset_id=None, user=None, **kwargs):
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
        url = '/dataset/{dataset}/resource/{resource}/download'.format(
            dataset=dataset_id,
            resource=resource_id,
        )
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_request_access_request(self, app, dataset_id, user, message, **kwargs):
        url = '/dataset/{}/request_access'.format(dataset_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.post(
            url,
            data={'message': message},
            extra_environ=env,
            **kwargs
        )
        return resp

    def make_dataset_publish_request(self, app, dataset_id, user=None, **kwargs):
        url = '/dataset/publish/{}'.format(dataset_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_dataset_publish_microdata_request(self, app, dataset_id, user=None, **kwargs):
        url = '/dataset/{}/publish_microdata'.format(dataset_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = app.post(url=url, extra_environ=env, **kwargs)
        return resp


    # Dataset Publish

    def test_publish_dataset_no_resources(self, app):
        draft_dataset = factories.Dataset(
            name='dataset2',
            title='Test Dataset 2',
            owner_org='container1',
            data_collection_technique = 'f2f',
            sampling_procedure = 'nonprobability',
            operational_purpose_of_data = 'cartography',
            user=self.user1,
            visibility='restricted',
            state='draft',
        )
        resp = self.make_dataset_publish_request(
            app,
            draft_dataset['id'],
            user='user1',
            status=400,
        )
        assert 'Dataset must have one or more resources to publish' in resp.body

    def test_publish_dataset_with_resources(self, app):
        draft_dataset = factories.Dataset(
            name='dataset2',
            title='Test Dataset 2',
            owner_org='container1',
            data_collection_technique = 'f2f',
            sampling_procedure = 'nonprobability',
            operational_purpose_of_data = 'cartography',
            user=self.user1,
            visibility='restricted',
            state='draft',
        )
        factories.Resource(
            name='resource1',
            package_id=draft_dataset['name'],
            url_type='upload',
            upload=mocks.FakeFileStorage(),
        )
        self.make_dataset_publish_request(
            app,
            draft_dataset['id'],
            user='user1',
            status=200,
        )

    # Dataset Copy

    def test_dataset_copy(self, app):
        resp = self.make_dataset_copy_request(
            app,
            dataset_id='dataset1',
            user='user1',
            status=200
        )
        assert 'action="/dataset/new"' in resp.body
        assert 'You are copying' in resp.body
        assert 'f2f' in resp.body
        assert 'nonprobability' in resp.body
        assert 'cartography' in resp.body
        assert 'Add Data' in resp.body
        assert 'container1' in resp.body

    def test_dataset_copy_to_other_org(self, app):
        resp = self.make_dataset_copy_request(
            app,
            dataset_id='dataset1',
            user='user2',
            status=200
        )
        assert 'action="/dataset/new"' in resp.body
        assert 'You are copying' in resp.body
        assert 'f2f' in resp.body
        assert 'nonprobability' in resp.body
        assert 'cartography' in resp.body
        assert 'Add Data' in resp.body
        assert 'container1' not in resp.body

    def test_dataset_copy_no_orgs(self, app):
        resp = self.make_dataset_copy_request(
            app,
            dataset_id='dataset1',
            user='user3',
            status=403
        )

    def test_dataset_copy_bad_dataset(self, app):
        resp = self.make_dataset_copy_request(
            app,
            dataset_id='bad',
            user='user1',
            status=404
        )

    # Resource Upload

    def test_edit_resource_works(self, app):
        url = toolkit.url_for(
            'resource.edit',
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

        resp = app.post(url, data=data, extra_environ=env, status=200)

        assert 'The form contains invalid entries:' not in resp.body

    def test_edit_resource_must_provide_upload(self, app):
        url = toolkit.url_for(
            'resource.edit',
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

        resp = app.post(url, data=data, extra_environ=env, status=200)

        assert 'The form contains invalid entries:' in resp.body
        assert 'All data resources require an uploaded file' in resp.body

    # Resource Copy

    def test_resource_copy(self, app):
        resp = self.make_resource_copy_request(
            app, dataset_id='dataset1', resource_id=self.resource1['id'], user='user1',
            status=200
        )
        assert 'action="/dataset/dataset1/resource/new"' in resp.body
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
            'package_collaborator_create',
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

    # Publish Microdata

    def test_publish_microdata_invalid_method(self, app):
        resp = app.get(
            '/dataset/dataset1/publish_microdata',
            extra_environ={'REMOTE_USER': 'user3'},
            status=404
        )

    def test_publish_microdata_valid(self, app):
        mock_action = mock.MagicMock(return_value={'url': 'http://foo.bar/baz'})
        with mock.patch('ckanext.unhcr.blueprints.dataset._call_publish_action', mock_action):
            resp = self.make_dataset_publish_microdata_request(
                app,
                dataset_id='dataset1',
                user='user1',
                status=200
            )
        mock_action.assert_called_once()
        assert (
            'published to the Microdata library at the following address: &#34;http://foo.bar/baz&#34;'
            in resp.body
        )

    def test_publish_microdata_errors(self, app):
        mock_action = mock.Mock()
        mock_action.side_effect = RuntimeError('oh no!')
        with mock.patch('ckanext.unhcr.blueprints.dataset._call_publish_action', mock_action):
            resp = self.make_dataset_publish_microdata_request(
                app,
                dataset_id='dataset1',
                user='user1',
                status=200
            )
        mock_action.assert_called_once()
        assert 'failed for the following reason: &#34;oh no!&#34;' in resp.body

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
                status=200
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

        assert (
            'Requested access to download resources from Test Dataset 1' in
            resp.body
        )

    def test_request_access_user_already_has_access(self, app):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                app, dataset_id='dataset1', user='user1', message='I can haz access?',
                status=200
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

        assert (
            'You already have access to download resources from Test Dataset 1' in
            resp.body
        )


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate', 'with_request_context')
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
        assert (
            'You are not authorized to download the resources from this dataset'
            in res.body
        )

        environ = {'REMOTE_USER': self.org_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)
        assert (
            'You are not authorized to download the resources from this dataset'
            not in res.body
        )

        environ = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)
        assert (
            'You are not authorized to download the resources from this dataset'
            not in res.body
        )

    def test_access_visibility_private_not_admin(self, app):

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

    def test_access_visibility_private_admin(self, app):
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
        # Even though we tried to save this with visibility='private'
        # this feature is disabled, so the validator has altered it for us
        # from now on the dataset should behave as 'restricted'
        assert dataset['visibility'] == 'restricted'

        url = toolkit.url_for('dataset_read', id=dataset['id'])

        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)
        assert (
            'You are not authorized to download the resources from this dataset'
            in res.body
        )

        environ = {'REMOTE_USER': self.org_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)
        assert (
            'You are not authorized to download the resources from this dataset'
            not in res.body
        )

        environ = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=200)
        assert (
            'You are not authorized to download the resources from this dataset'
            not in res.body
        )
