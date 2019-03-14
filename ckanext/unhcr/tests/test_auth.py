import pylons
from paste.registry import Registry
from nose.plugins.attrib import attr

from nose.tools import assert_in, assert_not_in, assert_raises, assert_equals
from ckan.plugins import toolkit
from ckan.tests import helpers
from ckan.tests import factories as core_factories

from ckanext.unhcr import auth
from ckanext.unhcr.tests import factories


# TODO: extract as a test base for all tests
class AuthTestBase(helpers.FunctionalTestBase):

    @classmethod
    def setup_class(cls):

        # Hack because the hierarchy extension uses c in some methods
        # that are called outside the context of a web request
        c = pylons.util.AttribSafeContextObj()
        registry = Registry()
        registry.prepare()
        registry.register(pylons.c, c)

        super(AuthTestBase, cls).setup_class()


class TestAuthUI(AuthTestBase):

    def test_non_logged_in_users(self):

        app = self._get_test_app()

        dataset = factories.Dataset()
        data_container = factories.DataContainer()

        endpoints = [
            ('/', 403),
            ('/dataset', 403),
            ('/dataset/{}'.format(dataset['name']), 404),
            ('/data-container', 403),
            ('/data-container/{}'.format(data_container['name']), 404),
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

        user1 = core_factories.User()
        user2 = core_factories.User()
        data_container = factories.DataContainer(
            users=[{'name': user1['name'], 'capacity': 'admin'}]
        )
        dataset = factories.Dataset(
            owner_org=data_container['id'],
            private=True
        )

        environ = {
            'REMOTE_USER': str(user1['name'])
        }

        response = app.get(
            '/dataset/{}'.format(dataset['name']), extra_environ=environ)
        assert_not_in('You must be logged in', response.body)

        environ = {
            'REMOTE_USER': str(user2['name'])
        }

        response = app.get(
            '/dataset/{}'.format(dataset['name']), extra_environ=environ,
            status=404)


class TestAuthAPI(AuthTestBase):

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


class TestAuthUnit(AuthTestBase):

    # Package

    def test_package_create(self):
        creator = core_factories.User(name='creator')
        deposit = factories.DataContainer(name='data-deposit')
        result = auth.package_create({'user': 'creator'}, {'owner_org': deposit['id']})
        assert_equals(result['success'], True)

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
