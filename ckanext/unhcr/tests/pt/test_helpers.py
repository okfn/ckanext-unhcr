# -*- coding: utf-8 -*-

import os
import pytest
from ckan import model
from ckan.plugins import toolkit
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories
from ckanext.unhcr import helpers


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestGetDataContainer(object):

    def test_get_data_container(self):
        container = factories.DataContainer(title='container1')
        result = helpers.get_data_container(container['id'])
        assert result['title'] == container['title']

    def test_get_data_container_not_found(self):
        with pytest.raises(toolkit.ObjectNotFound) as e:
            helpers.get_data_container('bad-id')


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestGetAllDataContainers(object):

    def test_get_all_data_containers(self):
        container1 = factories.DataContainer(title='container1')
        container2 = factories.DataContainer(title='container2')
        user = core_factories.User()
        result = helpers.get_all_data_containers(
            userobj=model.User.get(user['id'])
        )
        assert len(result) == 2
        assert result[0]['title'] == container1['title']
        assert result[1]['title'] == container2['title']

    def test_get_all_data_containers_exclude(self):
        container1 = factories.DataContainer(title='container1')
        container2 = factories.DataContainer(title='container2')
        user = core_factories.User()
        result = helpers.get_all_data_containers(
            exclude_ids=[container2['id']],
            userobj=model.User.get(user['id']),
        )
        assert len(result) == 1
        assert result[0]['title'] == 'container1'

    def test_get_all_data_containers_external_user(self):
        container1 = factories.DataContainer(title='container1', visible_external=True)
        container2 = factories.DataContainer(title='container2', visible_external=False)
        internal_user = core_factories.User()
        external_user = factories.ExternalUser()

        # internal_user can see all the containers
        assert(
            2 ==
            len(
                helpers.get_all_data_containers(
                    userobj=model.User.get(internal_user['id']),
                )
            )
        )

        # external_user can only see the container with visible_external by default
        assert (
            1 ==
            len(
                helpers.get_all_data_containers(
                    userobj=model.User.get(external_user['id']),
                )
            )
        )

        # ..but if we explicitly include the other container, we can see that too
        assert (
            2 ==
            len(
                helpers.get_all_data_containers(
                    userobj=model.User.get(external_user['id']),
                    include_ids=[container2['id']],
                )
            )
        )

    def test_get_all_data_containers_with_dataset(self):
        depadmin = core_factories.User()
        deposit = factories.DataContainer(
            id='data-deposit',
            users=[
                {'name': depadmin['name'], 'capacity': 'admin'},
            ]
        )
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')

        container_admin = core_factories.User()
        container1 = factories.DataContainer(title='container1', visible_external=False)
        container2 = factories.DataContainer(title='container2', visible_external=False)
        container3 = factories.DataContainer(title='container3', visible_external=False,
            users=[{'name': container_admin['name'], 'capacity': 'admin'}]
        )
        container4 = factories.DataContainer(title='container4', visible_external=False,
            users=[{'name': container_admin['name'], 'capacity': 'admin'}]
        )
        container5 = factories.DataContainer(title='container5', visible_external=False,
            users=[{'name': container_admin['name'], 'capacity': 'editor'}]
        )

        # if I'm creating a new dataset, I can see all the containers
        assert (
            5 ==
            len(
                helpers.get_all_data_containers(
                    userobj=model.User.get(container_admin['id']),
                    exclude_ids=[deposit['id']],
                    dataset=None,
                )
            )
        )

        # if I'm editing my own dataset, I can still see all the containers
        assert (
            5 ==
            len(
                helpers.get_all_data_containers(
                    userobj=model.User.get(container_admin['id']),
                    exclude_ids=[deposit['id']],
                    dataset={'creator_user_id': container_admin['id']}
                )
            )
        )

        # but if I'm editing someone else's dataset, I can only see containers I'm an admin of
        assert (
            2 ==
            len(
                helpers.get_all_data_containers(
                    userobj=model.User.get(container_admin['id']),
                    exclude_ids=[deposit['id']],
                    dataset={'creator_user_id': 'someone else'}
                )
            )
        )

        # ..unless we explicitly say to include others (which takes precedence)
        assert (
            3 ==
            len(
                helpers.get_all_data_containers(
                    userobj=model.User.get(container_admin['id']),
                    exclude_ids=[deposit['id']],
                    dataset={'creator_user_id': 'someone else'},
                    include_ids=[container2['id']],
                )
            )
        )

        # ..or we're a more priveledged user, in which case we can see all of them
        for user in [depadmin, sysadmin]:
            assert (
                5 ==
                len(
                    helpers.get_all_data_containers(
                        userobj=model.User.get(user['id']),
                        exclude_ids=[deposit['id']],
                        dataset={'creator_user_id': 'anyone'},
                    )
                )
            )


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestLinkedDatasets(object):

    def test_get_linked_datasets_for_form_none(self):
        user = core_factories.User()
        context = {'model': model, 'user': user['name']}

        linked_datasets = helpers.get_linked_datasets_for_form(
            context=context,
            user_id=user['id'],
        )

        assert linked_datasets == []

    def test_get_linked_datasets_for_form_many(self):
        user = core_factories.User()
        container1 = factories.DataContainer(title='container1', users=[user])
        container2 = factories.DataContainer(title='container2', users=[user])
        dataset1 = factories.Dataset(id='id1', title='dataset1', owner_org=container1['id'])
        dataset2 = factories.Dataset(id='id2', title='dataset2', owner_org=container2['id'])
        context = {'model': model, 'user': user['name']}

        linked_datasets = helpers.get_linked_datasets_for_form(
            context=context,
            user_id=user['id'],
        )

        assert linked_datasets == [
            {'text': 'container1', 'children': [{'text': 'dataset1', 'value': 'id1'}]},
            {'text': 'container2', 'children': [{'text': 'dataset2', 'value': 'id2'}]},
        ]

    def test_get_linked_datasets_for_form_many_selected_ids(self):
        user = core_factories.User(id='user_selected_ids', name='user_selected_ids')
        container1 = factories.DataContainer(title='container1', users=[user])
        container2 = factories.DataContainer(title='container2', users=[user])
        dataset1 = factories.Dataset(id='id1', title='dataset1', owner_org=container1['id'])
        dataset2 = factories.Dataset(id='id2', title='dataset2', owner_org=container2['id'])
        context = {'model': model, 'user': user['name']}

        linked_datasets = helpers.get_linked_datasets_for_form(
            context=context,
            user_id=user['id'],
            selected_ids=['id2']
        )

        assert linked_datasets == [
            {'text': 'container1', 'children': [{'text': 'dataset1', 'value': 'id1'}]},
            {'text': 'container2', 'children': [{'text': 'dataset2', 'value': 'id2', 'selected': 'selected'}]},
        ]

    def test_get_linked_datasets_for_form_many_exclude_ids(self):
        user = core_factories.User(id='user_exclude_ids', name='user_exclude_ids')
        container1 = factories.DataContainer(title='container1', users=[user])
        container2 = factories.DataContainer(title='container2', users=[user])
        dataset1 = factories.Dataset(id='id1', title='dataset1', owner_org=container1['id'])
        dataset2 = factories.Dataset(id='id2', title='dataset2', owner_org=container2['id'])
        context = {'model': model, 'user': user['name']}

        linked_datasets = helpers.get_linked_datasets_for_form(
            context=context,
            user_id=user['id'],
            exclude_ids=['id2']
        )

        assert linked_datasets == [
            {'text': 'container1', 'children': [{'text': 'dataset1', 'value': 'id1'}]},
        ]

    def test_get_linked_datasets_for_display_none(self):
        user = core_factories.User()
        context = {'model': model, 'user': user['name']}

        linked_datasets = helpers.get_linked_datasets_for_display('', context=context)

        assert linked_datasets == []

    def test_get_linked_datasets_for_display_one(self):
        url = os.environ.get('CKAN_SITE_URL', 'http://test.ckan.net')
        user = core_factories.User()
        dataset = factories.Dataset(name='name', title='title')
        context = {'model': model, 'user': user['name']}

        linked_datasets = helpers.get_linked_datasets_for_display(
            dataset['id'],
            context=context
        )

        assert linked_datasets == [
            {'href': '%s/dataset/name' % url, 'text': 'title'},
        ]

    def test_get_linked_datasets_for_display_many(self):
        url = os.environ.get('CKAN_SITE_URL', 'http://test.ckan.net')
        user = core_factories.User()
        dataset1 = factories.Dataset(name='name1', title='title1')
        dataset2 = factories.Dataset(name='name2', title='title2')
        context = {'model': model, 'user': user['name']}

        linked_datasets = helpers.get_linked_datasets_for_display(
            '{%s,%s}' % (dataset1['id'], dataset2['id']), context=context)

        assert linked_datasets == [
            {'href': '%s/dataset/name1' % url, 'text': 'title1'},
            {'href': '%s/dataset/name2' % url, 'text': 'title2'},
        ]


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestPendingRequests(object):
    # TODO: migrate from nose
    pass


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestDataDeposit(object):

    def test_get_data_deposit(self):
        deposit = factories.DataContainer(id='data-deposit')
        result = helpers.get_data_deposit()
        assert result['id'] == 'data-deposit'

    def test_get_data_deposit_not_created(self):
        result = helpers.get_data_deposit()
        assert result == {'id': 'data-deposit', 'name': 'data-deposit'}


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestDatasetValidationErrorOrNone(object):

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
        assert error.error_summary == {
            'Keywords': 'Select at least one',
            'Archived': 'Missing value',
            'Data collector': 'Missing value',
            'Unit of measurement': 'Missing value',
            'Data collection technique': 'Missing value',
            'External access level': 'Missing value',
        }

    def test_get_dataset_validation_error_or_none_valid(self):
        dataset = factories.Dataset(name='name', title='title')
        context = {'model': model, 'session': model.Session, 'ignore_auth': True ,'user': None}
        error = helpers.get_dataset_validation_error_or_none(dataset, context)
        assert error is None

    def test_convert_deposited_dataset_to_regular_dataset(self):
        deposited = {
            'type': 'deposited-dataset',
            'owner_org': 'id-data-deposit',
            'owner_org_dest': 'id-data-target',
        }
        regular = helpers.convert_deposited_dataset_to_regular_dataset(deposited)
        assert regular == {
            'type': 'dataset',
            'owner_org': 'id-data-target',
        }


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestMicrodataHelpers(object):

    def test_convert_dataset_to_microdata_survey(self):
        dataset = factories.Dataset(
            operational_purpose_of_data = 'cartography',
            name='dataset',
            maintainer = 'maintainer',
            maintainer_email = 'maintainer@email.com',
            version = '1',
            tags = [{'name': 'Keyword1'}, {'name': 'Keyword2'}],
            unit_of_measurement = 'individual',
            keywords = ['3', '4'],
            date_range_start = '2015-01-01',
            date_range_end = '2016-01-01',
            geog_coverage = 'world',
            data_collector = 'ACF,UNHCR',
            data_collection_technique = 'f2f',
            sampling_procedure = 'nonprobability',
            data_collection_notes = 'Notes about data collection',
            weight_notes = 'Notes about weight',
            clean_ops_notes = 'Notes about cleaning',
            response_rate_notes = 'Notes about response',
        )
        survey = helpers.convert_dataset_to_microdata_survey(dataset, nation='nation', repoid='repoid')
        assert survey == {
            'repositoryid': 'REPOID',
            'access_policy': 'na',
            'published': 0,
            'overwrite': 'no',
            'study_desc': {
                'title_statement': {
                    'idno': u'DATASET',
                    'title': u'Test Dataset'
                },
                'authoring_entity': [
                    {'affiliation': 'UNHCR', 'name': 'Office of the High Commissioner for Refugees'}
                ],
                'distribution_statement': {
                    'contact': [
                        {'name': 'maintainer', 'email': 'maintainer@email.com'},
                    ],
                },
                'version_statement': {
                    'version': '1',
                },
                'study_info': {
                    'keywords': [
                        {'keyword': 'Keyword1'},
                        {'keyword': 'Keyword2'},
                    ],
                    'topics': [
                        {'topic': 'Health'},
                        {'topic': 'Water Sanitation Hygiene'}
                    ],
                    'coll_dates': [
                        {'start': '2015-01-01', 'end': '2016-01-01'},
                    ],
                    'nation': [
                        {'name': 'nation'}
                    ],
                    'abstract': 'Just another test dataset.',
                    'geog_coverage': 'world',
                    'analysis_unit': 'individual',
                },
                'method': {
                    'data_collection': {
                        'data_collectors': [
                            {'name': 'ACF'},
                            {'name': 'UNHCR'},
                        ],
                        'sampling_procedure': 'Non-probability',
                        'coll_mode': 'Face-to-face interview',
                        'coll_situation': 'Notes about data collection',
                        'weight': 'Notes about weight',
                        'cleaning_operations': 'Notes about cleaning',
                    },
                    'analysis_info': {
                        'response_rate': 'Notes about response',
                    }
                },
            },
        }

    def test_convert_dataset_to_microdata_survey_minimal(self):
        dataset = factories.Dataset(
            operational_purpose_of_data = 'cartography',
            name='dataset',
            unit_of_measurement = 'individual',
            keywords = ['3', '4'],
            archived = 'False',
            data_collector = 'ACF,UNHCR',
            data_collection_technique = 'f2f',
            sampling_procedure = 'nonprobability',
        )
        survey = helpers.convert_dataset_to_microdata_survey(dataset, nation='nation', repoid='repoid')
        assert survey == {
            'repositoryid': 'REPOID',
            'access_policy': 'na',
            'published': 0,
            'overwrite': 'no',
            'study_desc': {
                'title_statement': {
                    'idno': u'DATASET',
                    'title': u'Test Dataset'
                },
                'authoring_entity': [
                    {'affiliation': 'UNHCR', 'name': 'Office of the High Commissioner for Refugees'}
                ],
                'study_info': {
                    'topics': [
                        {'topic': 'Health'},
                        {'topic': 'Water Sanitation Hygiene'}
                    ],
                    'nation': [
                        {'name': 'nation'}
                    ],
                    'abstract': 'Just another test dataset.',
                    'analysis_unit': 'individual',
                },
                'method': {
                    'data_collection': {
                        'data_collectors': [
                            {'name': 'ACF'},
                            {'name': 'UNHCR'},
                        ],
                        'sampling_procedure': 'Non-probability',
                        'coll_mode': 'Face-to-face interview',
                    },
                },
            },
        }
