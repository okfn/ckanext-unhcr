import json
import responses
from ckan import model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers, factories as core_factories
from nose.tools import assert_raises, assert_equals, nottest
from ckanext.unhcr.tests import base, factories, mocks
from ckanext.unhcr import helpers
from ckanext.unhcr.activity import log_download_activity


class TestActions(base.FunctionalTestBase):

    # General

    def setup(self):
        super(TestActions, self).setup()

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
        updated_resource = core_helpers.call_action('resource_update', {}, **resource)

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
            ['All data resources require an uploaded file'])
