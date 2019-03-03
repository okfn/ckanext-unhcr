import os
import pylons
from ckan import model
from ckan.plugins import toolkit
from paste.registry import Registry
from nose.plugins.attrib import attr
from ckan.tests import factories as core_factories
from nose.tools import assert_raises, assert_equals
from ckan.tests.helpers import call_action, FunctionalTestBase
from ckanext.unhcr.tests import factories
from ckanext.unhcr import validators


class TestValidators(FunctionalTestBase):

    # Config

    @classmethod
    def setup_class(cls):

        # Hack because the hierarchy extension uses c in some methods
        # that are called outside the context of a web request
        c = pylons.util.AttribSafeContextObj()
        registry = Registry()
        registry.prepare()
        registry.register(pylons.c, c)

        super(TestValidators, cls).setup_class()

    # Deposited Datasets

    def test_deposited_datset_owner_org(self):
        depo = factories.DataContainer(id='data-deposit')
        dest = factories.DataContainer(id='data-destination')
        result = validators.deposited_dataset_owner_org('data-deposit', {})
        assert_equals(result, 'data-deposit')

    def test_deposited_datset_owner_org_invalid(self):
        depo = factories.DataContainer(id='data-deposit')
        dest = factories.DataContainer(id='data-destination')
        assert_raises(toolkit.Invalid,
            validators.deposited_dataset_owner_org, 'data-destination', {})

    def test_deposited_datset_owner_org_dest(self):
        depo = factories.DataContainer(id='data-deposit')
        dest = factories.DataContainer(id='data-destination')
        result = validators.deposited_dataset_owner_org_dest('data-destination', {})
        assert_equals(result, 'data-destination')

    def test_deposited_datset_owner_org_dest_invalid_data_deposit(self):
        depo = factories.DataContainer(id='data-deposit')
        dest = factories.DataContainer(id='data-destination')
        assert_raises(toolkit.Invalid,
            validators.deposited_dataset_owner_org_dest, 'data-deposit', {})

    def test_deposited_datset_owner_org_dest_invalid_not_existent(self):
        depo = factories.DataContainer(id='data-deposit')
        dest = factories.DataContainer(id='data-destination')
        assert_raises(toolkit.Invalid,
            validators.deposited_dataset_owner_org_dest, 'not-existent', {})
