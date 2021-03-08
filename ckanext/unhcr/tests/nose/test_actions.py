import datetime
import json
import mock
import re
import responses
from ckan import model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers, factories as core_factories
from nose.tools import assert_raises, assert_equals, assert_true, assert_false, nottest
from ckanext.unhcr.tests import base, factories, mocks
from ckanext.unhcr import helpers
from ckanext.unhcr.activity import log_download_activity

assert_in = core_helpers.assert_in


class TestMicrodata(base.FunctionalTestBase):

    # General

    def setup(self):
        super(TestMicrodata, self).setup()

        # Config
        toolkit.config['ckanext.unhcr.microdata_api_key'] = 'API-KEY'

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.user = core_factories.User(name='user', id='user')

        # Datasets
        self.dataset = factories.Dataset(
            name='dataset')

    @responses.activate
    def test_package_publish_microdata(self):
        context = {'model': model, 'user': self.sysadmin['name']}

        # Patch requests
        url = 'https://microdata.unhcr.org/index.php/api/datasets/create/survey/DATASET'
        responses.add_passthru('http')
        responses.add(responses.POST, url, status=200,
            json={'status': 'success', 'dataset': {'id': 1},})

        # Publish to microdata
        survey = toolkit.get_action('package_publish_microdata')(context, {
            'id': self.dataset['id'],
            'nation': 'nation',
            'repoid': 'repoid',
        })

        # Check calls
        call = responses.calls[0]
        assert_equals(len(responses.calls), 1)
        assert_equals(call.request.url, url)
        assert_equals(call.request.headers['X-Api-Key'], 'API-KEY')
        assert_equals(call.request.headers['Content-Type'], 'application/json')
        assert_equals(json.loads(call.request.body), helpers.convert_dataset_to_microdata_survey(self.dataset, 'nation', 'repoid'))
        assert_equals(survey['url'], 'https://microdata.unhcr.org/index.php/catalog/1')

    @responses.activate
    def test_package_publish_microdata_not_valid_request(self):
        context = {'model': model, 'user': self.sysadmin['name']}

        # Patch requests
        url = 'https://microdata.unhcr.org/index.php/api/datasets/create/survey/DATASET'
        responses.add_passthru('http')
        responses.add(responses.POST, url, status=400,
            json={'status': 'failed'})

        # Publish to microdata
        with assert_raises(RuntimeError):
            toolkit.get_action('package_publish_microdata')(context, {
                'id': self.dataset['id'],
                'nation': '',
            })

    def test_package_publish_microdata_not_found(self):
        context = {'model': model, 'user': self.sysadmin['name']}
        action = toolkit.get_action('package_publish_microdata')
        assert_raises(toolkit.ObjectNotFound,
            action, context, {'id': 'bad-id'})

    def test_package_publish_microdata_not_sysadmin(self):
        context = {'model': model, 'user': self.user['name']}
        action = toolkit.get_action('package_publish_microdata')
        assert_raises(toolkit.NotAuthorized,
            action, context, {'id': self.dataset['id']})

    def test_package_publish_microdata_not_set_api_key(self):
        context = {'model': model, 'user': self.sysadmin['name']}
        action = toolkit.get_action('package_publish_microdata')
        del toolkit.config['ckanext.unhcr.microdata_api_key']
        assert_raises(toolkit.NotAuthorized,
            action, context, {'id': self.dataset['id']})


class TestPrivateResources(base.FunctionalTestBase):

    def setup(self):
        super(TestPrivateResources, self).setup()

        # Users
        self.normal_user = core_factories.User()
        self.org_user = core_factories.User()
        self.sysadmin = core_factories.Sysadmin()

        # Containers
        self.container = factories.DataContainer(
            users=[
                {'name': self.org_user['name'], 'capacity': 'member'}
            ]
        )

    def test_private_is_false_if_not_sysadmin(self):

        dataset = factories.Dataset(
            private=True, user=self.normal_user)

        assert_equals(dataset['private'], False)

    def test_private_can_be_true_if_sysadmin(self):

        dataset = factories.Dataset(
            private=True,
            visibility='private',
            user=self.sysadmin)

        assert_equals(dataset['private'], True)

    def test_access_visibility_public(self):

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

        app = self._get_test_app()

        # We don't have data but we pass authorization
        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=404)

    def test_access_visibility_restricted(self):

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

        app = self._get_test_app()

        # We don't pass authorization (forbidden)
        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=403)

    def test_access_visibility_restricted_pages_visible(self):

        dataset = factories.Dataset(
            visibility='restricted',
            owner_org=self.container['id'],
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )

        url = toolkit.url_for('dataset_read', id=dataset['id'])

        app = self._get_test_app()

        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ)
        assert_equals(res.status_int, 200)

        environ = {'REMOTE_USER': self.org_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ)
        assert_equals(res.status_int, 200)

        environ = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ)
        assert_equals(res.status_int, 200)

    def test_access_visibility_private(self):

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

        app = self._get_test_app()

        # We don't pass authorization (forbidden)
        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=403)

        # We don't have data but we pass authorization
        environ = {'REMOTE_USER': self.org_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=404)

        # We don't have data but we pass authorization
        environ = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=404)

    @nottest
    # TODO: activate
    # why is the private dataset still available in the test env
    def test_access_visibility_private_pages_not_visible(self):

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

        app = self._get_test_app()

        environ = {'REMOTE_USER': self.normal_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ, status=404)

        environ = {'REMOTE_USER': self.org_user['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ)
        assert_equals(res.status_int, 200)

        environ = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}
        res = app.get(url, extra_environ=environ)
        assert_equals(res.status_int, 200)


class TestPackageActivityList(base.FunctionalTestBase):

    def setup(self):
        super(TestPackageActivityList, self).setup()

        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.container1_admin = core_factories.User()
        self.container1_member = core_factories.User()
        self.container1 = factories.DataContainer(
            users=[
                {"name": self.container1_admin["name"], "capacity": "admin"},
                {"name": self.container1_member["name"], "capacity": "member"},
            ]
        )
        self.dataset1 = factories.Dataset(
            owner_org=self.container1["id"], visibility="private"
        )
        self.resource1 = factories.Resource(
            package_id=self.dataset1['id'],
            upload=mocks.FakeFileStorage(),
            url = "http://fakeurl/test.txt",
            url_type='upload',
        )
        helpers.create_curation_activity(
            'dataset_approved',
            self.dataset1['id'],
            self.dataset1['name'],
            self.sysadmin['id'],
            message='asdf'
        )
        log_download_activity({'user': self.sysadmin['name']}, self.resource1['id'])

    def test_container_admin(self):
        context = {
            'user': self.container1_admin['name'],
            'package': model.package.Package.get(self.dataset1['id'])
        }
        data_dict = {
            'id': self.dataset1['id'],
            'get_internal_activities': True
        }
        activities = toolkit.get_action('package_activity_list')(context, data_dict)
        # a container admin can see all the internal activities
        assert_equals(2, len(activities))
        assert_equals('download resource', activities[0]['activity_type'])
        assert_equals('dataset_approved', activities[1]['data']['curation_activity'])

    def test_dataset_editor(self):
        collaborator = core_factories.User()
        core_helpers.call_action(
            'dataset_collaborator_create',
            id=self.dataset1['id'],
            user_id=collaborator['id'],
            capacity='editor',
        )
        context = {
            'user': collaborator['name'],
            'package': model.package.Package.get(self.dataset1['id'])
        }
        data_dict = {
            'id': self.dataset1['id'],
            'get_internal_activities': True
        }
        activities = toolkit.get_action('package_activity_list')(context, data_dict)
        # a dataset editor can only see the curation activities
        assert_equals(1, len(activities))
        assert_equals('dataset_approved', activities[0]['data']['curation_activity'])

    def test_container_member(self):
        context = {
            'user': self.container1_member['name'],
            'package': model.package.Package.get(self.dataset1['id'])
        }
        data_dict = {
            'id': self.dataset1['id'],
            'get_internal_activities': True
        }
        action = toolkit.get_action('package_activity_list')
        # a container member can't see any internal activities
        assert_raises(toolkit.NotAuthorized, action, context, data_dict)

    def test_unprivileged_user(self):
        normal_user = core_factories.User()
        context = {
            'user': normal_user['name'],
            'package': model.package.Package.get(self.dataset1['id'])
        }
        data_dict = {
            'id': self.dataset1['id'],
            'get_internal_activities': True
        }
        action = toolkit.get_action('package_activity_list')
        # an unprivileged user can't see any internal activities
        assert_raises(toolkit.NotAuthorized, action, context, data_dict)


class TestDatastoreAuthRestrictedDownloads(base.FunctionalTestBase):

    def setup(self):
        super(TestDatastoreAuthRestrictedDownloads, self).setup()

        # Users
        self.normal_user = core_factories.User()
        self.org_user = core_factories.User()
        self.sysadmin = core_factories.Sysadmin()

        # Containers
        self.container = factories.DataContainer(
            users=[
                {'name': self.org_user['name'], 'capacity': 'member'},
            ]
        )

        # Datasets
        self.dataset = factories.Dataset(
            visibility='restricted',
            owner_org=self.container['id'],
        )
        self.resource = factories.Resource(
            package_id=self.dataset['id'],
            url_type='datastore',
        )

        # Actions
        core_helpers.call_action('datastore_create',
            resource_id=self.resource['id'],
            records=[{'a':1, 'b': 2}]
        )

    def _get_context(self, user):
        return {
            'user': user['name'],
            'model': model,
        }

    @nottest
    # TODO: activate
    # datastore doesn't seem ready after `datastore_create`
    def test_datastore_info_perms(self):

        context = self._get_context(self.normal_user)
        assert_raises(toolkit.NotAuthorized, core_helpers.call_auth,
            'datastore_info', context=context, id=self.resource['id'])

        context = self._get_context(self.org_user)
        assert core_helpers.call_auth('datastore_info', context=context,
            id=self.resource['id'])

        context = self._get_context(self.sysadmin)
        assert core_helpers.call_auth('datastore_info', context=context,
            id=self.resource['id'])

    @nottest
    # TODO: activate
    # datastore doesn't seem ready after `datastore_create`
    def test_datastore_search_perms(self):

        context = self._get_context(self.normal_user)
        assert_raises(toolkit.NotAuthorized, core_helpers.call_auth,
            'datastore_search', context=context,
            resource_id=self.resource['id'])

        context = self._get_context(self.org_user)
        assert core_helpers.call_auth('datastore_search', context=context,
            resource_id=self.resource['id'])

        context = self._get_context(self.sysadmin)
        assert core_helpers.call_auth('datastore_search', context=context,
            resource_id=self.resource['id'])

    @nottest
    # TODO: activate
    # datastore doesn't seem ready after `datastore_create`
    def test_datastore_search_sql_perms(self):

        context = self._get_context(self.normal_user)
        context['table_names'] = [self.resource['id']]
        assert_raises(toolkit.NotAuthorized, core_helpers.call_auth,
            'datastore_search_sql', context=context,
            resource_id=self.resource['id'])

        context = self._get_context(self.org_user)
        context['table_names'] = [self.resource['id']]
        assert core_helpers.call_auth('datastore_search_sql', context=context,
            resource_id=self.resource['id'])

        context = self._get_context(self.sysadmin)
        context['table_names'] = [self.resource['id']]
        assert core_helpers.call_auth('datastore_search_sql', context=context,
            resource_id=self.resource['id'])


class TestResourceUpload(base.FunctionalTestBase):

    def test_upload_present(self):

        dataset = factories.Dataset()

        resource = factories.Resource(
            package_id=dataset['id'],
            upload=mocks.FakeFileStorage(),
            url = "http://fakeurl/test.txt",
            url_type='upload',
        )

        assert_equals(
            resource['url'],
            '{}/dataset/{}/resource/{}/download/test.txt'.format(
                toolkit.config.get('ckan.site_url').rstrip('/'),
                dataset['id'],
                resource['id']
            )
        )

    def test_upload_present_after_update(self):

        dataset = factories.Dataset()

        resource = factories.Resource(
            package_id=dataset['id'],
            upload=mocks.FakeFileStorage(),
            url = "http://fakeurl/test.txt",
            url_type='upload',
        )

        resource['name'] = 'updated'
        updated_resource = core_helpers.call_action(
            'resource_update',
            {'ignore_auth': True},
            **resource
        )

        assert_equals(updated_resource['name'], 'updated')

        assert_equals(
            updated_resource['url'],
            '{}/dataset/{}/resource/{}/download/test.txt'.format(
                toolkit.config['ckan.site_url'].rstrip('/'),
                dataset['id'],
                resource['id']
            )
        )

    def test_upload_external_url_data(self):

        dataset = factories.Dataset()

        with assert_raises(toolkit.ValidationError) as exc:

            factories.Resource(
                type='data',
                package_id=dataset['id'],
                url='https://example.com/some.data.csv'
            )

        assert exc.exception.error_dict.keys() == ['url']

        assert_equals(
            exc.exception.error_dict['url'],
            ['All data resources require an uploaded file'])

    def test_upload_external_url_attachment(self):
        dataset = factories.Dataset()
        resource = factories.Resource(
            type='attachment',
            package_id=dataset['id'],
            url='https://example.com/some.data.csv',
            file_type='other'
        )

        # tbh, the main thing we're testing here is that the line above
        # runs without throwing a ValidationError
        # but I supposed we should assert _something_
        assert_equals(resource['url'], 'https://example.com/some.data.csv')

    def test_upload_missing(self):

        dataset = factories.Dataset()

        with assert_raises(toolkit.ValidationError) as exc:

            factories.Resource(package_id=dataset['id'])

        assert exc.exception.error_dict.keys() == ['url']

        assert_equals(
            exc.exception.error_dict['url'],
            ['All data resources require an uploaded file']
        )


class TestPendingRequestsList(base.FunctionalTestBase):
    def setup(self):
        super(TestPendingRequestsList, self).setup()

    def test_container_request_list(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        container1 = factories.DataContainer(
            name='container1',
            id='container1',
            state='approval_needed',
        )
        container2 = factories.DataContainer(
            name='container2',
            id='container2',
            state='approval_needed',
        )
        context = {'model': model, 'user': 'sysadmin'}
        requests = toolkit.get_action("container_request_list")(
            context, {'all_fields': False}
        )
        assert_equals(requests['count'], 2)
        assert_equals(requests['containers'], [container1['id'], container2['id']])

    def test_container_request_list_all_fields(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        container1 = factories.DataContainer(
            name='container1',
            id='container1',
            state='approval_needed',
        )
        context = {'model': model, 'user': 'sysadmin'}
        requests = toolkit.get_action("container_request_list")(
            context, {'all_fields': True}
        )
        assert_equals(requests['count'], 1)
        assert_equals(requests['containers'][0]['name'], 'container1')

    def test_container_request_list_empty(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        context = {'model': model, 'user': 'sysadmin'}
        requests = toolkit.get_action("container_request_list")(
            context, {'all_fields': True}
        )
        assert_equals(requests['count'], 0)
        assert_equals(requests['containers'], [])

    def test_container_request_list_not_authorized(self):
        user = core_factories.User(name='user', id='user')
        context = {'model': model, 'user': 'user'}
        with assert_raises(toolkit.NotAuthorized):
            toolkit.get_action("container_request_list")(
                context, {'all_fields': True}
            )


class TestExternalUserUpdateState(base.FunctionalTestBase):

    def setup(self):
        self.container1_admin = core_factories.User()
        self.container1 = factories.DataContainer(
            users=[{"name": self.container1_admin["name"], "capacity": "admin"}]
        )

    def test_target_user_is_internal(self):
        target_user = core_factories.User(
            state=model.State.PENDING,
        )
        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_target_user_is_not_pending(self):
        target_user = factories.ExternalUser()
        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_requesting_user_is_not_container_admin(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        access_request_data_dict = {
            'object_id': target_user['id'],
            'object_type': 'user',
            'message': 'asdf',
            'role': 'member',
            'data': {'default_containers': [self.container1['id']]}
        }
        toolkit.get_action(u'access_request_create')(
            {'user': target_user['id'], 'ignore_auth': True},
            access_request_data_dict
        )
        requesting_user = core_factories.User()

        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": requesting_user["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_requesting_user_is_not_admin_of_required_container(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        requesting_user = core_factories.User()
        container2 = factories.DataContainer(
            users=[{"name": requesting_user["name"], "capacity": "admin"}]
        )
        access_request_data_dict = {
            'object_id': target_user['id'],
            'object_type': 'user',
            'message': 'asdf',
            'role': 'member',
            'data': {'default_containers': [self.container1['id']]}
        }
        toolkit.get_action(u'access_request_create')(
            {'user': target_user['id'], 'ignore_auth': True},
            access_request_data_dict
        )

        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": requesting_user["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_no_access_request(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_invalid_state(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        access_request_data_dict = {
            'object_id': target_user['id'],
            'object_type': 'user',
            'message': 'asdf',
            'role': 'member',
            'data': {'default_containers': [self.container1['id']]}
        }
        toolkit.get_action(u'access_request_create')(
            {'user': target_user['id'], 'ignore_auth': True},
            access_request_data_dict
        )

        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.ValidationError,
            action,
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': 'foobar'}
        )

    def test_user_not_found(self):
        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.ObjectNotFound,
            action,
            {"user": self.container1_admin["name"]},
            {'id': 'does-not-exist', 'state': model.State.ACTIVE}
        )

    def test_success(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        access_request_data_dict = {
            'object_id': target_user['id'],
            'object_type': 'user',
            'message': 'asdf',
            'role': 'member',
            'data': {'default_containers': [self.container1['id']]}
        }
        toolkit.get_action(u'access_request_create')(
            {'user': target_user['id'], 'ignore_auth': True},
            access_request_data_dict
        )

        action = toolkit.get_action("external_user_update_state")
        action(
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

        user = toolkit.get_action("user_show")(
            {"ignore_auth": True}, {"id": target_user['id']}
        )
        assert_equals(model.State.ACTIVE, user['state'])


class TestPackageSearch(base.FunctionalTestBase):

    def test_package_search_permissions(self):
        internal_user = core_factories.User()
        external_user = factories.ExternalUser()
        dataset = factories.Dataset(private=True)
        action = toolkit.get_action("package_search")

        internal_user_search_result = action({'user': internal_user["name"]}, {})
        external_user_search_result = action({'user': external_user["name"]}, {})

        assert_equals(1, internal_user_search_result['count'])  # internal_user can see this
        assert_equals(0, external_user_search_result['count'])  # external_user can't


class TestDatasetCollaboratorCreate(base.FunctionalTestBase):

    def test_internal_user(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        internal_user = core_factories.User()
        dataset = factories.Dataset(private=True)

        toolkit.get_action("dataset_collaborator_create")(
            {'user': sysadmin['name']},
            {
                'id': dataset['id'],
                'user_id': internal_user['id'],
                'capacity': 'member',
            }
        )

        collabs_list = toolkit.get_action("dataset_collaborator_list_for_user")(
            {'user': sysadmin['name']},
            {'id': internal_user['id']}
        )
        assert_equals(dataset['id'], collabs_list[0]['dataset_id'])
        assert_equals('member', collabs_list[0]['capacity'])

    def test_external_user(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        external_user = factories.ExternalUser()
        dataset = factories.Dataset(private=True)

        action = toolkit.get_action("dataset_collaborator_create")
        assert_raises(
            toolkit.ValidationError,
            action,
            {'user': sysadmin['name']},
            {
                'id': dataset['id'],
                'user_id': external_user['id'],
                'capacity': 'member',
            }
        )


class TestClamAVActions(base.FunctionalTestBase):

    def setup(self):
        super(TestClamAVActions, self).setup()

        self.sysadmin = core_factories.Sysadmin()
        dataset = factories.Dataset()
        self.resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
            last_modified=datetime.datetime.utcnow(),
        )

    def get_task(self):
        return toolkit.get_action('task_status_show')(
            {'user': self.sysadmin['name']},
            {
                'entity_id': self.resource['id'],
                'task_type': 'clamav',
                'key': 'clamav'
            }
        )

    def insert_pending_task(self):
        return toolkit.get_action('task_status_update')(
            {'user': self.sysadmin['name']},
            {
                'entity_id': self.resource['id'],
                'entity_type': 'resource',
                'task_type': 'clamav',
                'last_updated': str(datetime.datetime.utcnow()),
                'state': 'pending',
                'key': 'clamav',
                'value': '{}',
                'error': 'null',
            }
        )

    @responses.activate
    @core_helpers.change_config('ckanext.unhcr.clamav_url', 'http://clamav:1234')
    def test_scan_submit_valid(self):
        responses.add_passthru(re.compile(r'^http:\/\/.*solr/.*$'))
        responses.add(responses.POST, 'http://clamav:1234/job', status=200)

        result = toolkit.get_action("scan_submit")(
            {'user': self.sysadmin['name']},
            {'id': self.resource['id']}
        )
        assert result

        assert responses.assert_call_count('http://clamav:1234/job', 1)
        request_body = json.loads(responses.calls[0].request.body)
        assert request_body['api_key']
        assert request_body['result_url'].endswith('/api/3/action/scan_hook')
        site_url = toolkit.config.get('ckan.site_url')
        assert site_url == request_body['metadata']['ckan_url']
        assert self.resource['id'] == request_body['metadata']['resource_id']

        task = self.get_task()
        assert u'pending' == task['state']

    @responses.activate
    @core_helpers.change_config('ckanext.unhcr.clamav_url', 'http://clamav:1234')
    def test_scan_submit_duplicate_task(self):
        responses.add_passthru(re.compile(r'^http:\/\/.*solr/.*$'))

        self.insert_pending_task()

        result = toolkit.get_action("scan_submit")(
            {'user': self.sysadmin['name']},
            {'id': self.resource['id']}
        )
        assert not(result)

    @responses.activate
    def test_scan_submit_base_url_not_set(self):
        responses.add_passthru(re.compile(r'^http:\/\/.*solr/.*$'))

        result = toolkit.get_action("scan_submit")(
            {'user': self.sysadmin['name']},
            {'id': self.resource['id']}
        )
        assert not(result)
        assert responses.assert_call_count('http://clamav:1234/job', 0)

        task = self.get_task()
        assert u'error' == task['state']

    @responses.activate
    @core_helpers.change_config('ckanext.unhcr.clamav_url', 'http://clamav:1234')
    def test_scan_submit_failure(self):
        responses.add_passthru(re.compile(r'^http:\/\/.*solr/.*$'))
        responses.add(responses.POST, 'http://clamav:1234/job', status=500)

        with assert_raises(toolkit.ValidationError):
            toolkit.get_action("scan_submit")(
                {'user': self.sysadmin['name']},
                {'id': self.resource['id']}
            )

        task = self.get_task()
        assert u'error' == task['state']

    def test_scan_submit_invalid_params(self):
        with assert_raises(toolkit.ValidationError):
            toolkit.get_action("scan_submit")(
                {'user': self.sysadmin['name']},
                {}
            )

    def test_scan_hook_complete_file_clean(self):
        self.insert_pending_task()

        mock_mailer = mock.Mock()
        with mock.patch('ckanext.unhcr.mailer.mail_user_by_id', mock_mailer):
            toolkit.get_action("scan_hook")(
                {'user': self.sysadmin['name']},
                {
                    "status": "complete",
                    "data": {
                        "status_code": 0,
                        "status_text": "SUCCESSFUL SCAN, FILE CLEAN",
                        "description": "/tmp/tmp37q_kv9u: OK\n\n----------- SCAN SUMMARY -----------\nKnown viruses: 8945669\nEngine version: 0.102.4\nScanned directories: 0\nScanned files: 1\nInfected files: 0\nData scanned: 0.00 MB\nData read: 0.00 MB (ratio 0.00:1)\nTime: 25.064 sec (0 m 25 s)\n"
                    },
                    "metadata": {
                        "resource_id": self.resource['id'],
                    }
                }
            )

        task = self.get_task()
        assert u'complete' == task['state']

        mock_mailer.assert_not_called()

    def test_scan_hook_complete_file_infected(self):
        self.insert_pending_task()

        mock_mailer = mock.Mock()
        with mock.patch('ckanext.unhcr.mailer.mail_user_by_id', mock_mailer):
            toolkit.get_action("scan_hook")(
                {'user': self.sysadmin['name']},
                {
                    "status": "complete",
                    "data": {
                        "status_code": 1,
                        "status_text": "SUCCESSFUL SCAN, FILE INFECTED",
                        "description": "/tmp/tmpmmy4xf83: Win.Test.EICAR_HDB-1 FOUND\n\n----------- SCAN SUMMARY -----------\nKnown viruses: 8945582\nEngine version: 0.102.4\nScanned directories: 0\nScanned files: 1\nInfected files: 1\nData scanned: 0.00 MB\nData read: 0.00 MB (ratio 0.00:1)\nTime: 27.025 sec (0 m 27 s)\n"
                    },
                    "metadata": {
                        "resource_id": self.resource['id'],
                    }
                }
            )

        task = self.get_task()
        assert u'complete' == task['state']

        mock_mailer.assert_called_once()

        assert self.sysadmin['id'] == mock_mailer.call_args[0][0]
        assert "[UNHCR RIDL] - Infected file found" == mock_mailer.call_args[0][1]
        assert "was scanned and found to be infected" in mock_mailer.call_args[0][2]
        assert "Win.Test.EICAR_HDB-1 FOUND" in mock_mailer.call_args[0][2]

    @core_helpers.change_config('ckanext.unhcr.error_emails', 'errors@okfn.org fred@example.com')
    def test_scan_hook_error(self):
        self.insert_pending_task()

        mock_mailer = mock.Mock()
        with mock.patch('ckan.lib.mailer.mail_recipient', mock_mailer):
            toolkit.get_action("scan_hook")(
                {'user': self.sysadmin['name']},
                {
                    "status": "error",
                    "data": None,
                    "error": {"message": "oh no"},
                    "metadata": {
                        "resource_id": self.resource['id'],
                    }
                }
            )

        task = self.get_task()
        assert u'error' == task['state']
        assert u'{"message": "oh no"}' == task['error']

        assert 2 == mock_mailer.call_count
        assert 'errors@okfn.org' == mock_mailer.call_args_list[0][0][1]
        assert 'fred@example.com' == mock_mailer.call_args_list[1][0][1]
        assert '[UNHCR RIDL] Error performing Clam AV Scan' == mock_mailer.call_args[0][2]

    def test_scan_hook_other(self):
        self.insert_pending_task()

        toolkit.get_action("scan_hook")(
            {'user': self.sysadmin['name']},
            {
                "status": "some other status",
                "metadata": {
                    "resource_id": self.resource['id'],
                }
            }
        )
        task = self.get_task()
        assert u'some other status' == task['state']

    @responses.activate
    @core_helpers.change_config('ckanext.unhcr.clamav_url', 'http://clamav:1234')
    def test_scan_hook_resubmit_not_required(self):
        responses.add_passthru(re.compile(r'^http:\/\/.*solr/.*$'))
        responses.add(responses.POST, 'http://clamav:1234/job', status=200)

        self.insert_pending_task()

        toolkit.get_action("scan_hook")(
            {'user': self.sysadmin['name']},
            {
                "status": "complete",
                "data": {
                    "status_code": 0,
                        "status_text": "SUCCESSFUL SCAN, FILE CLEAN",
                        "description": "/tmp/tmp37q_kv9u: OK...",
                },
                "metadata": {
                    "resource_id": self.resource['id'],
                    'original_url': self.resource['url'],
                    'task_created': self.resource['last_modified'],
                }
            }
        )

        assert responses.assert_call_count('http://clamav:1234/job', 0)

    @responses.activate
    @core_helpers.change_config('ckanext.unhcr.clamav_url', 'http://clamav:1234')
    def test_scan_hook_resubmit_required_changed_url(self):
        responses.add_passthru(re.compile(r'^http:\/\/.*solr/.*$'))
        responses.add(responses.POST, 'http://clamav:1234/job', status=200)

        self.insert_pending_task()

        toolkit.get_action("scan_hook")(
            {'user': self.sysadmin['name']},
            {
                "status": "complete",
                "data": {
                    "status_code": 0,
                        "status_text": "SUCCESSFUL SCAN, FILE CLEAN",
                        "description": "/tmp/tmp37q_kv9u: OK...",
                },
                "metadata": {
                    "resource_id": self.resource['id'],
                    'original_url': 'not the same url stored on the task'
                }
            }
        )

        assert responses.assert_call_count('http://clamav:1234/job', 1)

    @responses.activate
    @core_helpers.change_config('ckanext.unhcr.clamav_url', 'http://clamav:1234')
    def test_scan_hook_resubmit_required_more_recent_date(self):
        responses.add_passthru(re.compile(r'^http:\/\/.*solr/.*$'))
        responses.add(responses.POST, 'http://clamav:1234/job', status=200)

        self.insert_pending_task()

        toolkit.get_action("scan_hook")(
            {'user': self.sysadmin['name']},
            {
                "status": "complete",
                "data": {
                    "status_code": 0,
                        "status_text": "SUCCESSFUL SCAN, FILE CLEAN",
                        "description": "/tmp/tmp37q_kv9u: OK...",
                },
                "metadata": {
                    "resource_id": self.resource['id'],
                    'task_created': str(
                        datetime.datetime.strptime(
                            self.resource['last_modified'],
                            '%Y-%m-%dT%H:%M:%S.%f'
                        ) - datetime.timedelta(minutes=1)
                    ),
                }
            }
        )

        assert responses.assert_call_count('http://clamav:1234/job', 1)

    def test_scan_hook_invalid_params(self):
        with assert_raises(toolkit.ValidationError):
            toolkit.get_action("scan_hook")(
                {'user': self.sysadmin['name']},
                {}
            )
        with assert_raises(toolkit.ValidationError):
            toolkit.get_action("scan_hook")(
                {'user': self.sysadmin['name']},
                {
                    "status": "completed",
                }
            )
        with assert_raises(toolkit.ValidationError):
            toolkit.get_action("scan_hook")(
                {'user': self.sysadmin['name']},
                {
                    "status": "completed",
                    "metadata": {}
                }
            )


class TestHooks(base.FunctionalTestBase):

    def setup(self):
        super(TestHooks, self).setup()

        self.container = factories.DataContainer()
        self.dataset = factories.Dataset(owner_org=self.container['id'])
        self.resource = factories.Resource(
            package_id=self.dataset['id'],
            url_type='upload',
        )
        self.user = core_factories.Sysadmin()

        self.new_package_dict = {
            'external_access_level': 'public_use',
            'keywords': ['1'],
            'archived': 'False',
            'data_collector': 'test',
            'data_collection_technique': 'nf',
            'visibility': 'public',
            'name': 'test',
            'notes': 'test',
            'unit_of_measurement': 'test',
            'title': 'test',
            'owner_org': self.container['id'],
            'state': 'active',
        }
        self.new_resource_dict = {
            'package_id': self.dataset['id'],
            'upload': mocks.FakeFileStorage(),
            'url': 'http://fakeurl/test.txt',
            'url_type': 'upload',
            'type': 'data',
            'file_type': 'microdata',
            'identifiability': 'anonymized_public',
            'date_range_start': '2018-01-01',
            'date_range_end': '2019-01-01',
            'process_status': 'anonymized',
            'version': '1',
        }

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_create_resource_hook_called(self, mock_hook):
        action = toolkit.get_action("resource_create")
        resource = action({'user': self.user['name']}, self.new_resource_dict)
        mock_hook.assert_called_once()
        assert 'process_dataset_on_update' == mock_hook.call_args_list[0][0][0].__name__
        assert resource['package_id'] == mock_hook.call_args_list[0][0][1][0]

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_create_resource_hook_not_called(self, mock_hook):
        action = toolkit.get_action("resource_create")
        action({'user': self.user['name'], 'job': True}, self.new_resource_dict)
        mock_hook.assert_not_called()

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_create_package_hook_called(self, mock_hook):
        action = toolkit.get_action("package_create")
        dataset = action({'user': self.user['name']}, self.new_package_dict)
        mock_hook.assert_called_once()
        assert 'process_dataset_on_create' == mock_hook.call_args_list[0][0][0].__name__
        assert dataset['id'] == mock_hook.call_args_list[0][0][1][0]

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_create_package_hook_not_called_job(self, mock_hook):
        action = toolkit.get_action("package_create")
        dataset = action({'user': self.user['name'], 'job': True}, self.new_package_dict)
        mock_hook.assert_not_called()

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_create_package_hook_not_called_defer_commit(self, mock_hook):
        action = toolkit.get_action("package_create")
        dataset = action({'user': self.user['name'], 'defer_commit': True}, self.new_package_dict)
        mock_hook.assert_not_called()

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_create_package_hook_not_called_not_active(self, mock_hook):
        action = toolkit.get_action("package_create")
        self.new_package_dict['state'] = 'pending'
        dataset = action({'user': self.user['name']}, self.new_package_dict)
        mock_hook.assert_not_called()

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_update_resource_hook_called(self, mock_hook):
        action = toolkit.get_action("resource_update")
        action({'user': self.user['name']}, self.resource)
        mock_hook.assert_called_once()
        assert 'process_dataset_on_update' == mock_hook.call_args_list[0][0][0].__name__
        assert self.resource['package_id'] == mock_hook.call_args_list[0][0][1][0]

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_update_resource_hook_not_called(self, mock_hook):
        action = toolkit.get_action("resource_update")
        action({'user': self.user['name'], 'job': True}, self.resource)
        mock_hook.assert_not_called()

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_update_package_hook_called(self, mock_hook):
        action = toolkit.get_action("package_update")
        action({'user': self.user['name']}, self.dataset)
        mock_hook.assert_called_once()
        assert 'process_dataset_on_update' == mock_hook.call_args_list[0][0][0].__name__
        assert self.dataset['id'] == mock_hook.call_args_list[0][0][1][0]

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_update_package_hook_not_called(self, mock_hook):
        action = toolkit.get_action("package_update")
        action({'user': self.user['name'], 'job': True}, self.dataset)
        action({'user': self.user['name'], 'defer_commit': True}, self.dataset)
        self.dataset['state'] = 'pending'
        action({'user': self.user['name']}, self.dataset)
        mock_hook.assert_not_called()

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_delete_resource_hook_called(self, mock_hook):
        action = toolkit.get_action("resource_delete")

        action({'user': self.user['name']}, self.resource)
        mock_hook.assert_called_once()
        assert 'process_dataset_on_update' == mock_hook.call_args_list[0][0][0].__name__
        assert self.resource['package_id'] == mock_hook.call_args_list[0][0][1][0]

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_delete_resource_hook_not_called(self, mock_hook):
        action = toolkit.get_action("resource_delete")
        action({'user': self.user['name'], 'job': True}, self.resource)
        mock_hook.assert_not_called()

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_delete_package_hook_called(self, mock_hook):
        action = toolkit.get_action("package_delete")
        action({'user': self.user['name']}, self.dataset)
        assert 'process_dataset_on_delete' == mock_hook.call_args_list[0][0][0].__name__
        assert self.dataset['id'] == mock_hook.call_args_list[0][0][1][0]

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_after_delete_package_hook_not_called(self, mock_hook):
        action = toolkit.get_action("package_delete")
        action({'user': self.user['name'], 'job': True}, self.dataset)
        mock_hook.assert_not_called()
