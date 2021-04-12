# -*- coding: utf-8 -*-

import pytest
import mock
from ckan.plugins import toolkit
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories, mocks


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestHooks(object):

    def setup(self):
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
