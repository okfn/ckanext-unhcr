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

    def test_deposited_dataset_owner_org(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        result = validators.deposited_dataset_owner_org('data-deposit', {})
        assert_equals(result, 'data-deposit')

    def test_deposited_dataset_owner_org_invalid(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        assert_raises(toolkit.Invalid,
            validators.deposited_dataset_owner_org, 'data-target', {})

    def test_deposited_dataset_owner_org_dest(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        result = validators.deposited_dataset_owner_org_dest('data-target', {})
        assert_equals(result, 'data-target')

    def test_deposited_dataset_owner_org_dest_invalid_data_deposit(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        assert_raises(toolkit.Invalid,
            validators.deposited_dataset_owner_org_dest, 'data-deposit', {})

    def test_deposited_dataset_owner_org_dest_invalid_not_existent(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        assert_raises(toolkit.Invalid,
            validators.deposited_dataset_owner_org_dest, 'not-existent', {})

    def test_deposited_dataset_curation_state(self):
        assert_equals(validators.deposited_dataset_curation_state('draft', {}), 'draft')
        assert_equals(validators.deposited_dataset_curation_state('submitted', {}), 'submitted')
        assert_equals(validators.deposited_dataset_curation_state('review', {}), 'review')

    def test_deposited_dataset_curation_state_invalid(self):
        assert_raises(toolkit.Invalid,
            validators.deposited_dataset_curation_state, 'invalid', {})

    def test_deposited_dataset_curation_id_invalid(self):
        assert_raises(toolkit.Invalid,
            validators.deposited_dataset_curator_id, 'invalid', {})
