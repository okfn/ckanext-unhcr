import os
import pylons
from ckan import model
from ckan.plugins import toolkit
from paste.registry import Registry
from nose.plugins.attrib import attr
from ckan.tests import factories as core_factories
from nose.tools import assert_raises, assert_equals
from ckan.tests.helpers import call_action, FunctionalTestBase
from ckanext.unhcr.helpers import get_linked_datasets_for_form, get_linked_datasets_for_display
from ckanext.unhcr.tests import factories
from ckanext.unhcr import helpers


class TestHelpers(FunctionalTestBase):

    # Setup

    @classmethod
    def setup_class(cls):

        # Hack because the hierarchy extension uses c in some methods
        # that are called outside the context of a web request
        c = pylons.util.AttribSafeContextObj()
        registry = Registry()
        registry.prepare()
        registry.register(pylons.c, c)

        super(TestHelpers, cls).setup_class()

    # General

    def test_get_data_container(self):
        user = core_factories.User()
        context = {'model': model, 'user': user['name']}
        container = factories.DataContainer(title='container1')
        result = helpers.get_data_container(container['id'], context=context)
        assert_equals(result['title'], container['title'])

    def test_get_data_container_not_found(self):
        user = core_factories.User()
        context = {'model': model, 'user': user['name']}
        assert_raises(toolkit.ObjectNotFound,
            helpers.get_data_container, 'bad-id', context=context)

    def test_get_all_data_containers(self):
        container1 = factories.DataContainer(title='container1')
        container2 = factories.DataContainer(title='container2')
        result = helpers.get_all_data_containers()
        assert_equals(len(result), 2)
        assert_equals(result[0]['title'], container1['title'])
        assert_equals(result[1]['title'], container2['title'])

    def test_get_all_data_containers_exclude(self):
        container1 = factories.DataContainer(title='container1')
        container2 = factories.DataContainer(title='container2')
        result = helpers.get_all_data_containers(exclude_ids=[container2['id']])
        assert_equals(len(result), 1)
        assert_equals(result[0]['title'], 'container1')

    # Linked Datasets

    def test_get_linked_datasets_for_form_none(self):
        user = core_factories.User()
        context = {'model': model, 'user': user['name']}
        linked_datasets = get_linked_datasets_for_form(context=context, user_id=user['id'])
        assert_equals(linked_datasets, [])

    def test_get_linked_datasets_for_form_many(self):
        user = core_factories.User()
        container1 = factories.DataContainer(title='container1', users=[user])
        container2 = factories.DataContainer(title='container2', users=[user])
        dataset1 = factories.Dataset(id='id1', title='dataset1', owner_org=container1['id'])
        dataset2 = factories.Dataset(id='id2', title='dataset2', owner_org=container2['id'])
        context = {'model': model, 'user': user['name']}
        linked_datasets = get_linked_datasets_for_form(context=context, user_id=user['id'])
        assert_equals(linked_datasets, [
            {'text': 'container1', 'children': [{'text': 'dataset1', 'value': 'id1'}]},
            {'text': 'container2', 'children': [{'text': 'dataset2', 'value': 'id2'}]},
        ])

    def test_get_linked_datasets_for_form_many_selected_ids(self):
        user = core_factories.User(id='user_selected_ids', name='user_selected_ids')
        container1 = factories.DataContainer(title='container1', users=[user])
        container2 = factories.DataContainer(title='container2', users=[user])
        dataset1 = factories.Dataset(id='id1', title='dataset1', owner_org=container1['id'])
        dataset2 = factories.Dataset(id='id2', title='dataset2', owner_org=container2['id'])
        context = {'model': model, 'user': user['name']}
        linked_datasets = get_linked_datasets_for_form(context=context, user_id=user['id'], selected_ids=['id2'])
        assert_equals(linked_datasets, [
            {'text': 'container1', 'children': [{'text': 'dataset1', 'value': 'id1'}]},
            {'text': 'container2', 'children': [{'text': 'dataset2', 'value': 'id2', 'selected': 'selected'}]},
        ])

    def test_get_linked_datasets_for_form_many_exclude_ids(self):
        user = core_factories.User(id='user_exclude_ids', name='user_exclude_ids')
        container1 = factories.DataContainer(title='container1', users=[user])
        container2 = factories.DataContainer(title='container2', users=[user])
        dataset1 = factories.Dataset(id='id1', title='dataset1', owner_org=container1['id'])
        dataset2 = factories.Dataset(id='id2', title='dataset2', owner_org=container2['id'])
        context = {'model': model, 'user': user['name']}
        linked_datasets = get_linked_datasets_for_form(context=context, user_id=user['id'], exclude_ids=['id2'])
        assert_equals(linked_datasets, [
            {'text': 'container1', 'children': [{'text': 'dataset1', 'value': 'id1'}]},
        ])

    def test_get_linked_datasets_for_display_none(self):
        user = core_factories.User()
        context = {'model': model, 'user': user['name']}
        linked_datasets = get_linked_datasets_for_display('', context=context)
        assert_equals(linked_datasets, [])

    def test_get_linked_datasets_for_display_one(self):
        url = os.environ.get('CKAN_SITE_URL', 'http://test.ckan.net')
        user = core_factories.User()
        dataset = factories.Dataset(name='name', title='title')
        context = {'model': model, 'user': user['name']}
        linked_datasets = get_linked_datasets_for_display(dataset['id'], context=context)
        assert_equals(linked_datasets, [
            {'href': '%s/dataset/name' % url, 'text': 'title'},
        ])

    def test_get_linked_datasets_for_display_many(self):
        url = os.environ.get('CKAN_SITE_URL', 'http://test.ckan.net')
        user = core_factories.User()
        dataset1 = factories.Dataset(name='name1', title='title1')
        dataset2 = factories.Dataset(name='name2', title='title2')
        context = {'model': model, 'user': user['name']}
        linked_datasets = get_linked_datasets_for_display(
            '{%s,%s}' % (dataset1['id'], dataset2['id']), context=context)
        assert_equals(linked_datasets, [
            {'href': '%s/dataset/name1' % url, 'text': 'title1'},
            {'href': '%s/dataset/name2' % url, 'text': 'title2'},
        ])

    # Deposited Datasets

    def test_get_data_container_for_depositing(self):
        container = factories.DataContainer(id='data-deposit')
        result = helpers.get_data_container_for_depositing()
        assert_equals(result['id'], 'data-deposit')

    def test_get_data_container_for_depositing_not_created(self):
        result = helpers.get_data_container_for_depositing()
        assert_equals(result, {'id': 'data-deposit'})

    def test_get_dataset_validation_error_or_none(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        dataset = factories.DepositedDataset(
            name='name',
            title='title',
            owner_org=deposit['id'],
            owner_org_dest=target['id']
        )
        context = {'model': model, 'session': model.Session, 'ignore_auth': True ,'user': None}
        error = helpers.get_dataset_validation_error_or_none(dataset, context=context)
        assert_equals(error.error_summary, {
            'Keywords': 'Select at least one',
            'Archived': 'Missing value',
            'Data collector': 'Select at least one',
            'Unit of measurement': 'Missing value',
            'Data collection technique': 'Missing value',
        })

    def test_get_dataset_validation_error_or_none_valid(self):
        dataset = factories.Dataset(name='name', title='title')
        error = helpers.get_dataset_validation_error_or_none(dataset)
        assert_equals(error, None)

    def test_convert_deposited_dataset_to_regular_dataset(self):
        deposited = {
            'type': 'deposited-dataset',
            'owner_org': 'id-data-deposit',
            'owner_org_dest': 'id-data-target',
        }
        regular = helpers.convert_deposited_dataset_to_regular_dataset(deposited)
        assert_equals(regular, {
            'type': 'dataset',
            'owner_org': 'id-data-target',
        })
