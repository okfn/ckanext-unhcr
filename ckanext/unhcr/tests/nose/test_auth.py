import nose
import pylons
from paste.registry import Registry
from nose.plugins.attrib import attr

from nose.tools import assert_in, assert_not_in, assert_raises, assert_equals
import ckan.plugins as plugins
from ckan.plugins import toolkit
from ckan.tests import helpers
from ckan.tests import factories as core_factories

from ckanext.unhcr import auth
from ckanext.unhcr.helpers import convert_deposited_dataset_to_regular_dataset
from ckanext.unhcr.plugin import ALLOWED_ACTIONS
from ckanext.unhcr.tests import base, factories
from ckanext.unhcr.utils import get_module_functions


class TestAuthUI(base.FunctionalTestBase):

    def test_non_logged_in_users(self):
        app = self._get_test_app()

        dataset = factories.Dataset()
        data_container = factories.DataContainer()

        endpoints = [
            ('/', 403),
            ('/dataset', 403),
            ('/dataset/{}'.format(dataset['name']), 403),
            ('/data-container', 403),
            ('/data-container/{}'.format(data_container['name']), 403),
            ('/user', 403),
        ]
        for endpoint in endpoints:
            response = app.get(endpoint[0], status=endpoint[1])
            if endpoint[1] != 404:
                assert_in('You must be logged in', response.body)

    def test_logged_in_users(self):

        app = self._get_test_app()

        user = core_factories.User()
        dataset = factories.Dataset()
        data_container = factories.DataContainer()

        endpoints = [
            '/',
            '/dataset',
            '/dataset/{}'.format(dataset['name']),
            '/data-container',
            '/data-container/{}'.format(data_container['name']),
        ]

        environ = {
            'REMOTE_USER': str(user['name'])
        }

        for endpoint in endpoints:
            response = app.get(endpoint, extra_environ=environ)
            assert_not_in('You must be logged in', response.body)

    def test_logged_in_users_private_dataset(self):

        app = self._get_test_app()

        container_member = core_factories.User()
        dataset_member = core_factories.User()
        other_user = core_factories.User()
        data_container = factories.DataContainer(
            users=[{'name': container_member['name'], 'capacity': 'admin'}]
        )
        dataset = factories.Dataset(
            owner_org=data_container['id'],
            visibility='private'
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )
        helpers.call_action(
            'dataset_collaborator_create',
            id=dataset['id'],
            user_id=dataset_member['id'],
            capacity='member',
        )

        for user in [container_member, dataset_member]:
            response = app.get(
                '/dataset/{}'.format(dataset['name']),
                extra_environ={ 'REMOTE_USER': str(user['name']) },
                status=200,
            )
            # these users can see the dataset_read view
            assert_not_in('You must be logged in', response.body)
            # these users can also download the resource attached to dataset
            assert_not_in(
                'You are not authorized to download the resources from this dataset',
                response.body
            )

        response = app.get(
            '/dataset/{}'.format(dataset['name']),
            extra_environ={ 'REMOTE_USER': str(other_user['name']) },
            status=200,
        )
        # other_user is allowed to see the dataset_read view too
        assert_not_in('You must be logged in', response.body)
        # other_user is not allowed to download the resource
        assert_in(
            'You are not authorized to download the resources from this dataset',
            response.body
        )
        # but they can request access to it if they like
        assert_in(
            '<i class="fa fa-key"></i>Request Access',
            response.body
        )

    def test_external_users_endpoints(self):
        app = self._get_test_app()

        external_user = factories.ExternalUser()
        dataset = factories.Dataset()
        container = factories.DataContainer()
        deposit = factories.DataContainer(
            id='data-deposit',
            name='data-deposit'
        )
        env = {'REMOTE_USER': external_user['name'].encode('ascii')}

        endpoints_403 = [
            '/about',
            '/ckan-admin',
            '/dashboard',
            '/metrics',
            '/tag',
            '/dataset',
            '/data-container',
            '/organization',
            '/group',
            '/user',
        ]
        for endpoint in endpoints_403:
            resp = app.get(endpoint, extra_environ=env, status=403)

        endpoints_404 = [
            '/dataset/{}'.format(dataset['name']),
            '/data-container/{}'.format(container['name']),
            '/organization/{}'.format(container['name']),
            '/group/{}'.format(container['name']),
        ]
        for endpoint in endpoints_404:
            # these throw a 404 rather than a 403
            resp = app.get(endpoint, extra_environ=env, status=404)

        endpoints_200 = [
            '/',
            '/feeds/dataset.atom',
            '/data-container/data-deposit',
            '/api/2/util/resource/format_autocomplete?incomplete=a',
            '/api/2/util/tag/autocomplete?incomplete=a',
            '/user/{}'.format(external_user['name']),
        ]
        for endpoint in endpoints_200:
            resp = app.get(endpoint, extra_environ=env, status=200)


class TestAuthAPI(base.FunctionalTestBase):

    def test_non_logged_in_users(self):

        user = core_factories.User()
        data_container = factories.DataContainer(
            users=[{'name': user['name'], 'capacity': 'admin'}]
        )
        dataset = factories.Dataset(owner_org=data_container['id'])

        actions = [
            'package_search',
            'package_list',
            'organization_list',
            'group_list',
            'user_list',
            'organization_list_for_user',
        ]

        context = {
            'user': None,
            'ignore_auth': False
        }

        for action in actions:
            assert_raises(
                toolkit.NotAuthorized,
                helpers.call_action, action,
                context=context)

        assert_raises(
            toolkit.NotAuthorized,
            helpers.call_action, 'package_show',
            context=context, id=dataset['name'])

        assert_raises(
            toolkit.NotAuthorized,
            helpers.call_action, 'organization_show',
            context=context, id=data_container['name'])

        assert_raises(
            toolkit.NotAuthorized,
            helpers.call_action, 'user_show',
            context=context, id=user['id'])

    def test_logged_in_users(self):

        user = core_factories.User()

        actions = [
            'package_search',
            'package_list',
            'organization_list',
            'group_list',
            'user_list',
            'organization_list_for_user',
        ]

        context = {
            'user': user['name'],
            'ignore_auth': False
        }

        for action in actions:
            helpers.call_action(action, context=context)

        data_container = factories.DataContainer(
            users=[{'name': user['name'], 'capacity': 'admin'}]
        )
        dataset = factories.Dataset(owner_org=data_container['id'])

        helpers.call_action(
            'package_show', context=context, id=dataset['name'])

        helpers.call_action(
            'organization_show', context=context, id=data_container['name'])

        helpers.call_action(
            'user_show', context=context, id=user['id'])


class TestAuthUnit(base.FunctionalTestBase):

    # Package

    def test_resource_download(self):
        container_member = core_factories.User()
        dataset_member = core_factories.User()
        another_user = core_factories.User()
        data_container = factories.DataContainer(
            users=[{'name': container_member['name'], 'capacity': 'admin'}]
        )
        dataset = factories.Dataset(
            owner_org=data_container['id'],
            visibility='private'
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )
        helpers.call_action(
            'dataset_collaborator_create',
            id=dataset['id'],
            user_id=dataset_member['id'],
            capacity='member',
        )

        for user in [container_member, dataset_member]:
            assert_equals(
                {'success': True},
                auth.resource_download({'user': user['name']}, resource)
            )

        assert_equals(
            {'success': False},
            auth.resource_download({'user': another_user['name']}, resource)
        )

    def test_resource_download_deposited_dataset(self):
        depadmin = core_factories.User()
        curator = core_factories.User()
        target_container_admin = core_factories.User()
        target_container_member = core_factories.User()
        other_container_admin = core_factories.User()

        deposit = factories.DataContainer(
            id='data-deposit',
            users=[
                {'name': depadmin['name'], 'capacity': 'admin'},
                {'name': curator['name'], 'capacity': 'editor'},
            ]
        )
        target = factories.DataContainer(
            users=[
                {'name': target_container_admin['name'], 'capacity': 'admin'},
                {'name': target_container_member['name'], 'capacity': 'member'},
            ]
        )
        container = factories.DataContainer(
            users=[
                {'name': other_container_admin['name'], 'capacity': 'admin'},
            ]
        )

        dataset = factories.DepositedDataset(
            owner_org=deposit['id'],
            owner_org_dest=target['id']
        )
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )

        for user in [depadmin, curator, target_container_admin]:
            assert_equals(
                {'success': True},
                auth.resource_download({'user': user['name']}, resource)
            )

        for user in [target_container_member, other_container_admin]:
            assert_equals(
                {'success': False},
                auth.resource_download({'user': user['name']}, resource)
            )

    def test_external_users_core_actions(self):
        external_user = factories.ExternalUser()

        core_auth_modules = [
            'ckan.logic.auth.create',
            'ckan.logic.auth.delete',
            'ckan.logic.auth.get',
            'ckan.logic.auth.patch',
            'ckan.logic.auth.update',
        ]

        for module_path in core_auth_modules:
            actions = get_module_functions(module_path)
            for action in actions:
                context = {'user': external_user['name']}
                if action not in ALLOWED_ACTIONS:
                    assert_raises(
                        toolkit.NotAuthorized,
                        toolkit.check_access,
                        action,
                        context=context
                    )

    def test_external_users_plugin_actions(self):
        external_user = factories.ExternalUser()

        for plugin in plugins.PluginImplementations(plugins.IAuthFunctions):
            for action in plugin.get_auth_functions().keys():
                context = {'user': external_user['name']}
                if action not in ALLOWED_ACTIONS:
                    assert_raises(
                        toolkit.NotAuthorized,
                        toolkit.check_access,
                        action,
                        context=context
                    )

    def test_external_users_always_allowed_actions(self):
        external_user = factories.ExternalUser()

        # these actions should always return True,
        # regardless of the content of data_dict
        actions = [
            'format_autocomplete',
            'package_search',
            'group_list_authz',
            'organization_list_for_user',
            'tag_autocomplete',
            'tag_list',
        ]
        context = {'user': external_user['name']}

        for action in actions:
            assert_equals(True, toolkit.check_access(action, context))

    def test_organization_show(self):
        external_user = factories.ExternalUser()
        internal_user = core_factories.User()
        container = factories.DataContainer()
        deposit = factories.DataContainer(
            id='data-deposit',
            name='data-deposit'
        )

        # Everyone can see the data deposit
        assert_equals(
            True,
            toolkit.check_access(
                'organization_show',
                {'user': internal_user['name']},
                {'id': deposit['id']}
            )
        )
        assert_equals(
            True,
            toolkit.check_access(
                'organization_show',
                {'user': external_user['name']},
                {'id': deposit['id']}
            )
        )

        # Only internal users can see other containers
        assert_equals(
            True,
            toolkit.check_access(
                'organization_show',
                {'user': internal_user['name']},
                {'id': container['id']}
            )
        )
        assert_raises(
            toolkit.NotAuthorized,
            toolkit.check_access,
            'organization_show',
            context={'user': external_user['name']},
            data_dict={'id': container['id']}
        )

    def test_external_user_approved_deposit(self):
        external_user = factories.ExternalUser()

        target = factories.DataContainer(
            id='data-target',
            name='data-target',
        )
        deposit = factories.DataContainer(
            id='data-deposit',
            name='data-deposit'
        )

        deposited_dataset = factories.DepositedDataset(
            name='dataset1',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=external_user
        )
        tmp = deposited_dataset.copy()
        tmp.update({
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })
        deposited_dataset = helpers.call_action(
            'package_update',
            **tmp
        )

        # While the dataset is in deposited state, external_user can view it
        assert_equals(
            True,
            toolkit.check_access(
                'package_show',
                {'user': external_user['name']},
                {'id': deposited_dataset['id']},
            )
        )

        # Approve the dataset
        approved_dataset = convert_deposited_dataset_to_regular_dataset(deposited_dataset)
        approved_dataset = helpers.call_action(
            'package_update',
            context={'user': 'sysadmin', 'type': approved_dataset['type']},
            **approved_dataset
        )

        # Now that the dataset has moved out of the data-deposit,
        # external_user can not view it anymore
        assert_raises(
            toolkit.NotAuthorized,
            toolkit.check_access,
            'package_show',
            context={'user': external_user['name']},
            data_dict={'id': approved_dataset['id']},
        )

    def test_package_update(self):

        # Create users
        depadmin = core_factories.User(name='depadmin')
        curator = core_factories.User(name='curator')
        depositor = core_factories.User(name='depositor')
        creator = core_factories.User(name='creator')

        # Create containers
        deposit = factories.DataContainer(
            id='data-deposit',
            name='data-deposit',
            users=[
                {'name': 'depadmin', 'capacity': 'admin'},
                {'name': 'curator', 'capacity': 'editor'},
            ],
        )
        target = factories.DataContainer(
            id='data-target',
            name='data-target',
        )

        # Create dataset
        dataset = factories.DepositedDataset(
            name='dataset',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=creator
        )

        # Forbidden depadmin/curator/depositor
        assert_raises(
            toolkit.NotAuthorized,
            toolkit.check_access,
            'package_update',
            context={'user': 'depadmin'},
            data_dict={'id': dataset['id']},
        )
        assert_raises(
            toolkit.NotAuthorized,
            toolkit.check_access,
            'package_update',
            context={'user': 'curator'},
            data_dict={'id': dataset['id']},
        )
        assert_raises(
            toolkit.NotAuthorized,
            toolkit.check_access,
            'package_update',
            context={'user': 'depositor'},
            data_dict={'id': dataset['id']},
        )

        # Granted creator
        assert_equals(
            True,
            toolkit.check_access(
                'package_update',
                {'user': 'creator'},
                {'id': dataset['id']}
            )
        )


class TestPackageCreateAuth(base.FunctionalTestBase):

    def setup(self):
        super(TestPackageCreateAuth, self).setup()
        factories.DataContainer(
            id='data-deposit',
            name='data-deposit',
        )
        factories.DataContainer(
            id='data-target',
            name='data-target',
        )

    def test_unit_data_deposit(self):
        creator = core_factories.User(name='creator')
        result = auth.package_create(
            {'user': 'creator'}, {'owner_org': 'data-deposit'}
        )
        assert_equals(result['success'], True)

    def test_unit_user_is_container_admin(self):
        creator = core_factories.User(name='creator')
        container = factories.DataContainer(
            users=[
                {'name': 'creator', 'capacity': 'admin'},
            ],
        )
        result = auth.package_create(
            {'user': 'creator'}, {'owner_org': container['name']}
        )
        assert_equals(result['success'], True)

    def test_unit_user_is_not_container_admin(self):
        creator = core_factories.User(name='creator')
        container1 = factories.DataContainer(
            users=[
                {'name': 'creator', 'capacity': 'member'},
            ],
        )
        result = auth.package_create(
            {'user': 'creator'}, {'owner_org': container1['name']}
        )
        assert_equals(result['success'], False)

        container2 = factories.DataContainer()
        result = auth.package_create(
            {'user': 'creator'}, {'owner_org': container2['name']}
        )
        assert_equals(result['success'], False)

    def test_unit_no_data_dict(self):
        creator = core_factories.User(name='creator')
        result = auth.package_create({'user': 'creator'}, None)
        assert_equals(result['success'], False)

    @helpers.change_config('ckan.auth.create_unowned_dataset', False)
    def test_integration_new_deposit(self):
        # everyone can create datasets in the data-deposit
        external_user = factories.ExternalUser()
        resp = self.app.get(
            url='/deposited-dataset/new',
            extra_environ={'REMOTE_USER': external_user['name'].encode('ascii')},
            status=200,
        )

        internal_user = core_factories.User()
        resp = self.app.get(
            url='/deposited-dataset/new',
            extra_environ={'REMOTE_USER': internal_user['name'].encode('ascii')},
            status=200,
        )

    @helpers.change_config('ckan.auth.create_unowned_dataset', False)
    def test_integration_new_dataset(self):
        external_user = factories.ExternalUser()
        # external_user can't create a new dataset
        resp = self.app.get(
            url='/dataset/new',
            extra_environ={'REMOTE_USER': external_user['name'].encode('ascii')},
            status=403,
        )

        internal_user = core_factories.User()
        # internal_user can't create a dataset
        # because they aren't an admin of any containers
        resp = self.app.get(
            url='/dataset/new',
            extra_environ={'REMOTE_USER': internal_user['name'].encode('ascii')},
            status=403,
        )

        factories.DataContainer(
            users=[{'name': internal_user['name'], 'capacity': 'admin'}]
        )
        # now that internal_user is a container admin
        # they can create a dataset
        resp = self.app.get(
            url='/dataset/new',
            extra_environ={'REMOTE_USER': internal_user['name'].encode('ascii')},
            status=200,
        )

    @helpers.change_config('ckan.auth.create_unowned_dataset', False)
    def test_integration_edit_deposit(self):
        # everyone can edit their own draft deposited datasets
        external_user = factories.ExternalUser()
        external_deposit = factories.DepositedDataset(
            name='dataset1',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=external_user,
            state='draft',
        )
        resp = self.app.get(
            url='/deposited-dataset/edit/{}'.format(external_deposit['id']),
            extra_environ={'REMOTE_USER': external_user['name'].encode('ascii')},
            status=200,
        )

        internal_user = core_factories.User()
        internal_deposit = factories.DepositedDataset(
            name='dataset2',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=internal_user,
            state='draft',
        )
        resp = self.app.get(
            url='/deposited-dataset/edit/{}'.format(internal_deposit['id']),
            extra_environ={'REMOTE_USER': internal_user['name'].encode('ascii')},
            status=200,
        )


class TestExternalUserPackageAuths(base.FunctionalTestBase):

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
        assert_equals(
            True,
            toolkit.check_access(
                action,
                {'user': self.external_user['name']},
                data_dict,
            )
        )

    def assert_auth_fail(self, action, data_dict):
        assert_raises(
            toolkit.NotAuthorized,
            toolkit.check_access,
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

class TestUserAuth(base.FunctionalTestBase):

    def setup(self):
        super(TestUserAuth, self).setup()
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
        assert_raises(
            toolkit.NotAuthorized,
            toolkit.check_access,
            'user_show',
            context={'user': self.external_user['name']},
            data_dict={'id': self.internal_user['name']},
        )
        assert_raises(
            toolkit.NotAuthorized,
            toolkit.check_access,
            'user_show',
            context={'user': self.external_user['name']},
            data_dict={'id': self.sysadmin['name']},
        )
