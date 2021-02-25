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
