import os
import nose
import pylons
from ckan import model
from ckan.plugins import toolkit
from paste.registry import Registry
from nose.plugins.attrib import attr
from ckan.tests import factories as core_factories
from nose.tools import assert_raises, assert_equals, assert_in
from ckan.tests.helpers import call_action
from ckanext.unhcr.helpers import get_linked_datasets_for_form, get_linked_datasets_for_display
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import base, factories
from ckanext.unhcr import helpers


class TestHelpers(base.FunctionalTestBase):

    # General

    def test_get_data_container(self):
        container = factories.DataContainer(title='container1')
        result = helpers.get_data_container(container['id'])
        assert_equals(result['title'], container['title'])

    def test_get_data_container_not_found(self):
        assert_raises(toolkit.ObjectNotFound,
            helpers.get_data_container, 'bad-id')

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

    def test_get_all_data_containers_external_user(self):
        container1 = factories.DataContainer(title='container1', visible_external=True)
        container2 = factories.DataContainer(title='container2', visible_external=False)
        assert_equals(len(helpers.get_all_data_containers(external_user=True)), 1)
        assert_equals(len(helpers.get_all_data_containers(external_user=False)), 2)

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

    # Pending Requests

    def test_get_pending_requests_total(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        pending_container1 = factories.DataContainer(
            name='container1',
            id='container1',
            state='approval_needed',
        )
        pending_container2 = factories.DataContainer(
            name='container2',
            id='container2',
            state='approval_needed',
        )
        container3 = factories.DataContainer()
        dataset1 = factories.Dataset(
            owner_org=container3["id"], visibility="private"
        )
        requesting_user = core_factories.User()
        model.Session.add(
            AccessRequest(
                user_id=requesting_user["id"],
                object_id=container3["id"],
                object_type="organization",
                message="",
                role="member",
            )
        )
        model.Session.add(
            AccessRequest(
                user_id=requesting_user["id"],
                object_id=dataset1["id"],
                object_type="package",
                message="",
                role="member",
            )
        )
        model.Session.commit()

        # sysadmin can see/approve all 4 requests:
        # 2 x new container
        # 1 x container access
        # 1 x new dataset
        context = {'model': model, 'user': 'sysadmin'}
        count = helpers.get_pending_requests_total(context=context)
        assert_equals(count, 4)

        # but user can't see/approve any of them
        user = core_factories.User(name='user', id='user')
        context = {'model': model, 'user': 'user'}
        count = helpers.get_pending_requests_total(context=context)
        assert_equals(count, 0)

    def test_get_pending_requests_total_empty(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        context = {'model': model, 'user': 'sysadmin'}
        count = helpers.get_pending_requests_total(context=context)
        assert_equals(count, 0)

    # Deposited Datasets

    def test_get_data_deposit(self):
        deposit = factories.DataContainer(id='data-deposit')
        result = helpers.get_data_deposit()
        assert_equals(result['id'], 'data-deposit')

    def test_get_data_deposit_not_created(self):
        result = helpers.get_data_deposit()
        assert_equals(result, {'id': 'data-deposit', 'name': 'data-deposit'})

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
            'Data collector': 'Missing value',
            'Unit of measurement': 'Missing value',
            'Data collection technique': 'Missing value',
            'External access level': 'Missing value',
        })

    def test_get_dataset_validation_error_or_none_valid(self):
        dataset = factories.Dataset(name='name', title='title')
        context = {'model': model, 'session': model.Session, 'ignore_auth': True ,'user': None}
        error = helpers.get_dataset_validation_error_or_none(dataset, context)
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

    # Publishing

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
        assert_equals(survey, {
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
        })

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
        assert_equals(survey, {
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
        })


class TestDepositedDatasetHelpers(base.FunctionalTestBase):

    def setup(self):
        super(TestDepositedDatasetHelpers, self).setup()

        self.depadmin = core_factories.User()
        self.curator = core_factories.User()
        self.target_container_admin = core_factories.User()
        self.target_container_member = core_factories.User()
        self.other_container_admin = core_factories.User()
        self.depositor = core_factories.User()

        deposit = factories.DataContainer(
            id='data-deposit',
            users=[
                {'name': self.depadmin['name'], 'capacity': 'admin'},
                {'name': self.curator['name'], 'capacity': 'editor'},
            ]
        )
        target = factories.DataContainer(
            users=[
                {'name': self.target_container_admin['name'], 'capacity': 'admin'},
                {'name': self.target_container_member['name'], 'capacity': 'member'},
            ]
        )
        container = factories.DataContainer(
            users=[
                {'name': self.other_container_admin['name'], 'capacity': 'admin'},
            ]
        )

        self.draft_dataset = factories.DepositedDataset(
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            creator_user_id=self.depositor['id'],
            user=self.depositor,
            curation_state='draft',
        )
        self.submitted_dataset = factories.DepositedDataset(
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            creator_user_id=self.depositor['id'],
            user=self.depositor,
            curation_state='submitted',
        )
        self.review_dataset = factories.DepositedDataset(
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            creator_user_id=self.depositor['id'],
            user=self.depositor,
            curation_state='review',
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_admin(self):
        assert_equals(
            'admin',
            helpers.get_deposited_dataset_user_curation_role(
                self.depadmin['id'],
                self.draft_dataset,
            )
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_curator(self):
        assert_equals(
            'curator',
            helpers.get_deposited_dataset_user_curation_role(
                self.curator['id'],
                self.draft_dataset,
            )
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_container_admin(self):
        assert_equals(
            'container admin',
            helpers.get_deposited_dataset_user_curation_role(
                self.target_container_admin['id'],
                self.draft_dataset,
            )
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_depositor(self):
        assert_equals(
            'depositor',
            helpers.get_deposited_dataset_user_curation_role(
                self.depositor['id'],
                self.draft_dataset,
            )
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_user(self):
        for user in [self.target_container_member, self.other_container_admin]:
            assert_equals(
                'user',
                helpers.get_deposited_dataset_user_curation_role(
                    user['id'],
                    self.draft_dataset,
                )
            )

    def test_get_deposited_dataset_user_curation_role_without_dataset_admin(self):
        assert_equals(
            'admin',
            helpers.get_deposited_dataset_user_curation_role(self.depadmin['id'])
        )

    def test_get_deposited_dataset_user_curation_role_without_dataset_curator(self):
        assert_equals(
            'curator',
            helpers.get_deposited_dataset_user_curation_role(self.curator['id'])
        )

    def test_get_deposited_dataset_user_curation_role_without_dataset_container_admin(self):
        for user in [self.target_container_admin, self.other_container_admin]:
            assert_equals(
                'container admin',
                helpers.get_deposited_dataset_user_curation_role(user['id'])
            )

    def test_get_deposited_dataset_user_curation_role_without_dataset_depositor(self):
        for user in [self.target_container_member, self.depositor]:
            assert_equals(
                'depositor',
                helpers.get_deposited_dataset_user_curation_role(user['id'])
            )

    def test_get_deposited_dataset_user_curation_status_admin_draft(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.draft_dataset,
            self.depadmin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('draft', status['state'])
        assert_equals('admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_admin_submitted(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.submitted_dataset,
            self.depadmin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals(['edit', 'reject', 'assign', 'request_changes'], status['actions'])
        assert_equals('submitted', status['state'])
        assert_equals('admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_admin_review(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.review_dataset,
            self.depadmin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('review', status['state'])
        assert_equals('admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_curator_draft(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.draft_dataset,
            self.curator['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('draft', status['state'])
        assert_equals('curator', status['role'])

    def test_get_deposited_dataset_user_curation_status_curator_submitted(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.submitted_dataset,
            self.curator['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals(['edit', 'reject', 'request_changes'], status['actions'])
        assert_equals('submitted', status['state'])
        assert_equals('curator', status['role'])

    def test_get_deposited_dataset_user_curation_status_curator_review(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.review_dataset,
            self.curator['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('review', status['state'])
        assert_equals('curator', status['role'])

    def test_get_deposited_dataset_user_curation_status_container_admin_draft(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.draft_dataset,
            self.target_container_admin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('draft', status['state'])
        assert_equals('container admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_container_admin_submitted(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.submitted_dataset,
            self.target_container_admin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals(['edit', 'reject', 'request_changes'], status['actions'])
        assert_equals('submitted', status['state'])
        assert_equals('container admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_container_admin_review(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.review_dataset,
            self.target_container_admin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('review', status['state'])
        assert_equals('container admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_depositor_draft(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.draft_dataset,
            self.depositor['id'],
        )

        assert_equals(True, status['is_depositor'])
        assert_equals(['edit', 'submit', 'withdraw'], status['actions'])
        assert_equals('draft', status['state'])
        assert_equals('depositor', status['role'])

    def test_get_deposited_dataset_user_curation_status_depositor_submitted(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.submitted_dataset,
            self.depositor['id'],
        )

        assert_equals(True, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('submitted', status['state'])
        assert_equals('depositor', status['role'])

    def test_get_deposited_dataset_user_curation_status_depositor_review(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.review_dataset,
            self.depositor['id'],
        )

        assert_equals(True, status['is_depositor'])
        assert_equals(['request_changes'], status['actions'])
        assert_equals('review', status['state'])
        assert_equals('depositor', status['role'])

    def test_get_deposited_dataset_user_curation_status_user_draft(self):
        for user in [self.target_container_member, self.other_container_admin]:
            status = helpers.get_deposited_dataset_user_curation_status(
                self.draft_dataset,
                user['id'],
            )

            assert_equals(False, status['is_depositor'])
            assert_equals([], status['actions'])
            assert_equals('draft', status['state'])
            assert_equals('user', status['role'])

    def test_get_deposited_dataset_user_curation_status_user_submitted(self):
        for user in [self.target_container_member, self.other_container_admin]:
            status = helpers.get_deposited_dataset_user_curation_status(
                self.submitted_dataset,
                user['id'],
            )

            assert_equals(False, status['is_depositor'])
            assert_equals([], status['actions'])
            assert_equals('submitted', status['state'])
            assert_equals('user', status['role'])

    def test_get_deposited_dataset_user_curation_status_user_review(self):
        for user in [self.target_container_member, self.other_container_admin]:
            status = helpers.get_deposited_dataset_user_curation_status(
                self.review_dataset,
                user['id'],
            )

            assert_equals(False, status['is_depositor'])
            assert_equals([], status['actions'])
            assert_equals('review', status['state'])
            assert_equals('user', status['role'])

    def test_get_data_curation_users_no_container_admin(self):
        curators = helpers.get_data_curation_users({})
        curator_names = [
            curator['name'] for curator in curators
            # Added to org by ckan
            if not curator['sysadmin']
        ]
        assert_equals(len(curator_names), 2)
        assert_in(self.depadmin['name'], curator_names)
        assert_in(self.curator['name'], curator_names)

    def test_get_data_curation_users_with_container_admin(self):
        curators = helpers.get_data_curation_users(self.draft_dataset)
        curator_names = [
            curator['name'] for curator in curators
            # Added to org by ckan
            if not curator['sysadmin']
        ]
        assert_equals(len(curator_names), 3)
        assert_in(self.depadmin['name'], curator_names)
        assert_in(self.curator['name'], curator_names)
        assert_in(self.target_container_admin['name'], curator_names)
