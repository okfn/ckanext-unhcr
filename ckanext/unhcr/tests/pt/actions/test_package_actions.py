# -*- coding: utf-8 -*-

import pytest
import json
import responses
from ckan import model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories, mocks
from ckanext.unhcr import helpers
from ckanext.unhcr.activity import log_download_activity


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestMicrodata(object):

    # General

    def setup(self):
        # Config
        toolkit.config['ckanext.unhcr.microdata_api_key'] = 'API-KEY'

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.user = core_factories.User(name='user', id='user')

        # Datasets
        self.dataset = factories.Dataset(name='dataset')

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
        assert len(responses.calls) == 1
        assert call.request.url == url
        assert call.request.headers['X-Api-Key'] == 'API-KEY'
        assert call.request.headers['Content-Type'] == 'application/json'
        assert (
            json.loads(call.request.body) ==
            helpers.convert_dataset_to_microdata_survey(self.dataset, 'nation', 'repoid')
        )
        assert survey['url'] == 'https://microdata.unhcr.org/index.php/catalog/1'

    @responses.activate
    def test_package_publish_microdata_not_valid_request(self):
        context = {'model': model, 'user': self.sysadmin['name']}

        # Patch requests
        url = 'https://microdata.unhcr.org/index.php/api/datasets/create/survey/DATASET'
        responses.add_passthru('http')
        responses.add(responses.POST, url, status=400,
            json={'status': 'failed'})

        # Publish to microdata
        with pytest.raises(RuntimeError):
            toolkit.get_action('package_publish_microdata')(context, {
                'id': self.dataset['id'],
                'nation': '',
            })

    def test_package_publish_microdata_not_found(self):
        context = {'model': model, 'user': self.sysadmin['name']}
        action = toolkit.get_action('package_publish_microdata')
        with pytest.raises(toolkit.ObjectNotFound):
            action(context, {'id': 'bad-id'})

    def test_package_publish_microdata_not_sysadmin(self):
        context = {'model': model, 'user': self.user['name']}
        action = toolkit.get_action('package_publish_microdata')
        with pytest.raises(toolkit.NotAuthorized):
            action(context, {'id': self.dataset['id']})

    def test_package_publish_microdata_not_set_api_key(self):
        context = {'model': model, 'user': self.sysadmin['name']}
        action = toolkit.get_action('package_publish_microdata')
        del toolkit.config['ckanext.unhcr.microdata_api_key']
        with pytest.raises(toolkit.NotAuthorized):
            action(context, {'id': self.dataset['id']})


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestPackageActivityList(object):

    def setup(self):
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
            owner_org=self.container1["id"], visibility="restricted"
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
        assert 2 == len(activities)
        assert 'download resource' == activities[0]['activity_type']
        assert 'dataset_approved' == activities[1]['data']['curation_activity']

    def test_dataset_editor(self):
        collaborator = core_factories.User()
        core_helpers.call_action(
            'package_collaborator_create',
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
        assert 1 == len(activities)
        assert 'dataset_approved' == activities[0]['data']['curation_activity']

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
        with pytest.raises(toolkit.NotAuthorized):
            action(context, data_dict)

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
        with pytest.raises(toolkit.NotAuthorized):
            action(context, data_dict)


@pytest.mark.usefixtures('clean_db', 'clean_index', 'unhcr_migrate')
class TestPackageSearch(object):

    def test_package_search_permissions(self):
        internal_user = core_factories.User()
        external_user = factories.ExternalUser()
        dataset = factories.Dataset(private=True)
        action = toolkit.get_action("package_search")

        internal_user_search_result = action({'user': internal_user["name"]}, {})
        external_user_search_result = action({'user': external_user["name"]}, {})

        assert 1 == internal_user_search_result['count']  # internal_user can see this
        assert 0 == external_user_search_result['count']  # external_user can't


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestDatasetCollaboratorCreate(object):

    def test_internal_user(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        internal_user = core_factories.User()
        dataset = factories.Dataset()

        toolkit.get_action("package_collaborator_create")(
            {'user': sysadmin['name']},
            {
                'id': dataset['id'],
                'user_id': internal_user['id'],
                'capacity': 'member',
            }
        )

        collabs_list = toolkit.get_action("package_collaborator_list_for_user")(
            {'user': sysadmin['name']},
            {'id': internal_user['id']}
        )
        assert dataset['id'] == collabs_list[0]['package_id']
        assert 'member' == collabs_list[0]['capacity']

    def test_external_user(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        external_user = factories.ExternalUser()
        dataset = factories.Dataset()

        action = toolkit.get_action("package_collaborator_create")
        with pytest.raises(toolkit.ValidationError):
            action(
                {'user': sysadmin['name']},
                {
                    'id': dataset['id'],
                    'user_id': external_user['id'],
                    'capacity': 'member',
                }
            )
