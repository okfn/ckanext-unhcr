import mock
import pylons
from paste.registry import Registry
from nose.plugins.attrib import attr
from ckan.lib.helpers import url_for
from ckan.lib.search import rebuild
from ckan.logic import NotFound
from ckan.plugins import toolkit
from nose.tools import assert_raises, assert_equals, nottest
from ckan.tests import helpers as core_helpers, factories as core_factories
from ckanext.unhcr.tests import factories


class TestDepositedDatasetController(core_helpers.FunctionalTestBase):

    # Config

    @classmethod
    def setup_class(cls):

        # Hack because the hierarchy extension uses c in some methods
        # that are called outside the context of a web request
        c = pylons.util.AttribSafeContextObj()
        registry = Registry()
        registry.prepare()
        registry.register(pylons.c, c)

        core_helpers.reset_db()
        super(TestDepositedDatasetController, cls).setup_class()

    @classmethod
    def teardown_class(cls):
        super(TestDepositedDatasetController, cls).teardown_class()
        core_helpers.reset_db()

    def setup(self):
        super(TestDepositedDatasetController, self).setup()
        core_helpers.reset_db()
        rebuild()

        # Create users
        regular = core_factories.User(name='regular', id='regular')
        creator = core_factories.User(name='creator', id='creator')
        curator = core_factories.User(name='curator', id='curator')
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')

        # Create containers
        deposit = factories.DataContainer(
            users=[{'name': 'curator', 'capacity': 'editor'}],
            name='data-deposit',
            id='data-deposit'
        )
        target = factories.DataContainer(
            name='data-target',
            id='data-target'
        )

        # Create deposited dataset
        self.dataset = factories.DepositedDataset(
            name='dataset',
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            user=creator)

    # NotFound

    def test_deposited_dataset_action_404_for_bad_id(self):
        app = self._get_test_app()
        for command in ['approve', 'reject']:
            url = '/deposited-dataset/%s/%s' % ('bad-id', command)
            with assert_raises(toolkit.ObjectNotFound):
                app.get(url=url, status=404)

    # Forbidden

    def test_deposited_dataset_action_403_for_anonimous_user(self):
        app = self._get_test_app()
        for command in ['approve', 'reject']:
            url = '/deposited-dataset/%s/%s' % (self.dataset['id'], command)
            with assert_raises(toolkit.NotAuthorized):
                app.get(url=url, status=403)

    def test_deposited_dataset_action_403_for_regular_user(self):
        app = self._get_test_app()
        for command in ['approve', 'reject']:
            url = '/deposited-dataset/%s/%s' % (self.dataset['id'], command)
            env = {'REMOTE_USER': 'regular'.encode('ascii')}
            with assert_raises(toolkit.NotAuthorized):
                app.get(url=url, status=403, extra_environ=env)

    def test_deposited_dataset_action_403_for_creator_user(self):
        app = self._get_test_app()
        for command in ['approve', 'reject']:
            url = '/deposited-dataset/%s/%s' % (self.dataset['id'], command)
            env = {'REMOTE_USER': 'creator'.encode('ascii')}
            with assert_raises(toolkit.NotAuthorized):
                app.get(url=url, status=403, extra_environ=env)

    # Invalid

    # TODO: recover; it breaks session somewhow
    #  def test_deposited_dataset_approve_403_for_curator_or_sysadmin_user(self):
        #  for user in ['curator', 'sysadmin']:
            #  yield self.check_deposited_dataset_approve_403_for_curator_or_sysadmin_user, user

    #  def check_deposited_dataset_approve_403_for_curator_or_sysadmin_user(self, user):
        #  app = self._get_test_app()
        #  url = '/deposited-dataset/%s/approve' % self.dataset['id']
        #  env = {'REMOTE_USER': user.encode('ascii')}
        #  with assert_raises(toolkit.NotAuthorized):
            #  resp = app.get(url=url, status=403, extra_environ=env)

    # Approved

    def test_deposited_dataset_approve_for_curator_or_sysadmin_user(self):
        for user in ['curator', 'sysadmin']:
            yield self.check_deposited_dataset_approve_for_curator_or_sysadmin_user, user

    def check_deposited_dataset_approve_for_curator_or_sysadmin_user(self, user):

        # Fill missing fields
        dataset = self.dataset.copy()
        dataset.update({
            'unit_of_measurement': 'individual',
            'keywords': ['shelter', 'health'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
        })
        dataset = core_helpers.call_action('package_update', {'user': user}, **dataset)

        # Approve dataset
        app = self._get_test_app()
        url = '/deposited-dataset/%s/approve' % self.dataset['id']
        extra_environ = {'REMOTE_USER': user.encode('ascii')}
        resp = app.get(url=url, extra_environ=extra_environ)

        # Assert it's approved/updated
        assert_equals(resp.status_int, 302)
        approved_dataset = core_helpers.call_action(
            'package_show', {'user': 'creator'}, id=self.dataset['id'])
        assert_equals(approved_dataset['type'], 'dataset')
        assert_equals(approved_dataset['owner_org'], 'data-target')

    # Rejected

    def test_deposited_dataset_reject_for_curator_or_sysadmin_user(self):
        for user in ['curator', 'sysadmin']:
            yield self.check_deposited_dataset_reject_for_curator_or_sysadmin_user, user

    def check_deposited_dataset_reject_for_curator_or_sysadmin_user(self, user):

        # Reject dataset
        app = self._get_test_app()
        url = '/deposited-dataset/%s/reject' % self.dataset['id']
        extra_environ = {'REMOTE_USER': user.encode('ascii')}
        resp = app.get(url=url, extra_environ=extra_environ)

        # Assert it's purged
        assert_equals(resp.status_int, 302)
        with assert_raises(toolkit.ObjectNotFound):
            dataset = core_helpers.call_action(
                'package_show', {'user': 'creator'}, id=self.dataset['id'])
