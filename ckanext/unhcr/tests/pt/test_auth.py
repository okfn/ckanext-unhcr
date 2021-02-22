# -*- coding: utf-8 -*-

import pytest
from ckan.plugins import toolkit
from ckan.tests import factories as core_factories
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestExternalUserPackageAuths(object):

    def setup(self):
        self.external_user = factories.ExternalUser()
        user = core_factories.User()

        target = factories.DataContainer(
            id='data-target',
            name='data-target',
        )
        deposit = factories.DataContainer(
            id='data-deposit',
            name='data-deposit'
        )

        self.external_user_dataset = factories.DepositedDataset(
            description='deposited dataset created by external user',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=self.external_user
        )
        self.internal_user_dataset = factories.DepositedDataset(
            description='deposited dataset created by internal user',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=user
        )
        self.dataset = factories.Dataset(
            owner_org=target['id'],
            visibility='private'
        )

        self.external_dataset_resources = [
            factories.Resource(
                description='resource created by external_user attached to deposited dataset created by external_user',
                package_id=self.external_user_dataset['id'],
                url_type='upload',
                user=self.external_user,
            ),
            factories.Resource(
                description='resource created by someone else attached to deposited dataset created by external_user',
                package_id=self.external_user_dataset['id'],
                url_type='upload',
                user=user
            ),
        ]
        self.internal_dataset_resources = [
            factories.Resource(
                package_id=self.internal_user_dataset['id'],
                url_type='upload',
                user=user
            ),
        ]
        self.arbitrary_resource = factories.Resource(
            package_id=self.dataset['id'],
            url_type='upload',
        )

    def assert_auth_pass(self, action, data_dict):
        assert toolkit.check_access(
            action,
            context={'user': self.external_user['name']},
            data_dict=data_dict,
        )

    def assert_auth_fail(self, action, data_dict):
        with pytest.raises(toolkit.NotAuthorized):
            toolkit.check_access(
                action,
                context={'user': self.external_user['name']},
                data_dict=data_dict,
            )

    def test_package_actions(self):
        package_actions = [
            'package_delete',
            'package_patch',
            'package_show',
            'package_update',
        ]
        for action in package_actions:
            self.assert_auth_pass(action, {'id': self.external_user_dataset['id']})
            self.assert_auth_fail(action, {'id': self.internal_user_dataset['id']})
            self.assert_auth_fail(action, {'id': self.dataset['id']})

    def test_resource_create(self):
        self.assert_auth_pass('resource_create', {'package_id': self.external_user_dataset['id']})
        self.assert_auth_fail('resource_create', {'package_id': self.internal_user_dataset['id']})
        self.assert_auth_fail('resource_create', {'package_id': self.dataset['id']})

    def test_resource_actions(self):
        resource_actions = [
            'resource_delete',
            'resource_download',
            'resource_patch',
            'resource_show',
            'resource_update',
            'resource_view_list',
        ]
        for action in resource_actions:

            for resource in self.external_dataset_resources:
                self.assert_auth_pass(action, {
                    'package_id': self.external_user_dataset['id'],
                    'id': resource['id'],
                })

            for resource in self.internal_dataset_resources:
                self.assert_auth_fail(action, {
                    'package_id': self.internal_user_dataset['id'],
                    'id': resource['id'],
                })

            self.assert_auth_fail(action, {
                'package_id': self.dataset['id'],
                'id': self.arbitrary_resource['id'],
            })


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestUserAuth(object):

    def setup(self):
        self.sysadmin = core_factories.Sysadmin()
        self.external_user = factories.ExternalUser()
        self.internal_user = core_factories.User()

    def test_user_show_internal_user(self):
        assert toolkit.check_access(
            'user_show',
            {'user': self.internal_user['name']},
            {'id': self.internal_user['name']},
        )
        assert toolkit.check_access(
            'user_show',
            {'user': self.internal_user['name']},
            {'id': self.external_user['name']},
        )
        assert toolkit.check_access(
            'user_show',
            {'user': self.internal_user['name']},
            {'id': self.sysadmin['name']},
        )

    def test_user_show_external_user(self):
        assert toolkit.check_access(
            'user_show',
            {'user': self.external_user['name']},
            {'id': self.external_user['name']},
        )
        with pytest.raises(toolkit.NotAuthorized):
            toolkit.check_access(
                'user_show',
                context={'user': self.external_user['name']},
                data_dict={'id': self.internal_user['name']},
            )
        with pytest.raises(toolkit.NotAuthorized):
            toolkit.check_access(
                'user_show',
                context={'user': self.external_user['name']},
                data_dict={'id': self.sysadmin['name']},
            )
