import nose
import pylons
from paste.registry import Registry
from nose.plugins.attrib import attr

from nose.tools import assert_in, assert_not_in, assert_raises, assert_equals
from ckan.plugins import toolkit
from ckan.tests import helpers
from ckan.tests import factories as core_factories

from ckanext.unhcr import auth
from ckanext.unhcr.tests import base, factories


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
        external_user = core_factories.User()
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
            extra_environ={ 'REMOTE_USER': str(external_user['name']) },
            status=200,
        )
        # external_user is allowed to see the dataset_read view too
        assert_not_in('You must be logged in', response.body)
        # external_user is not allowed to download the resource
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

        external_user = core_factories.User(email='fred@externaluser.com')
        dataset = factories.Dataset()
        container = factories.DataContainer()
        env = {'REMOTE_USER': external_user['name'].encode('ascii')}

        endpoints_403 = [
            '/',
            '/about',
            '/ckan-admin',
            '/dashboard',
            '/metrics',
            '/tag',
            '/dataset',
            '/data-container',
            '/organization',
            '/group',
        ]
        for endpoint in endpoints_403:
            resp = app.get(endpoint, extra_environ=env, status=403)

        endpoints_404 = [
            '/dataset/{}'.format(dataset['name']),
            '/data-container/data-deposit',
            '/data-container/{}'.format(container['name']),
            '/organization/{}'.format(container['name']),
            '/group/{}'.format(container['name']),
        ]
        for endpoint in endpoints_404:
            # these throw a 404 rather than a 403
            resp = app.get(endpoint, extra_environ=env, status=404)

        endpoints_200 = [
            '/feeds/dataset.atom',
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

    def test_package_create(self):
        creator = core_factories.User(name='creator')
        deposit = factories.DataContainer(name='data-deposit')
        result = auth.package_create({'user': 'creator'}, {'owner_org': deposit['id']})
        assert_equals(result['success'], True)

    def test_resource_download(self):
        container_member = core_factories.User()
        dataset_member = core_factories.User()
        external_user = core_factories.User()
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
            auth.resource_download({'user': external_user['name']}, resource)
        )

    # TODO: fix problems with context pupulation
    #  def test_package_update(self):

        #  # Create users
        #  depadmin = core_factories.User(name='depadmin')
        #  curator = core_factories.User(name='curator')
        #  depositor = core_factories.User(name='depositor')
        #  creator = core_factories.User(name='creator')

        #  # Create containers
        #  deposit = factories.DataContainer(
            #  id='data-deposit',
            #  name='data-deposit',
            #  users=[
                #  {'name': 'depadmin', 'capacity': 'admin'},
                #  {'name': 'curator', 'capacity': 'editor'},
            #  ],
        #  )
        #  target = factories.DataContainer(
            #  id='data-target',
            #  name='data-target',
        #  )

        #  # Create dataset
        #  dataset = factories.DepositedDataset(
            #  name='dataset',
            #  owner_org='data-deposit',
            #  owner_org_dest='data-target',
            #  user=creator)

        #  # Forbidden depadmin/curator/depositor
        #  assert_equals(auth.package_update({'user': 'depadmin'}, dataset), False)
        #  assert_equals(auth.package_update({'user': 'curator'}, dataset), False)
        #  assert_equals(auth.package_update({'user': 'depositor'}, dataset), False)

        #  # Granted creator
        #  assert_equals(auth.package_update({'user': 'creator'}, dataset), True)
