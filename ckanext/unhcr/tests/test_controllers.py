import mock
from nose.plugins.attrib import attr
from ckan.lib.helpers import url_for
from ckan.logic import NotFound
from ckan.plugins import toolkit
from nose.tools import assert_raises, assert_equals, nottest
from ckan.tests import helpers as core_helpers, factories as core_factories
from ckanext.unhcr.tests import base, factories


# TODO: optimize testing speed
class TestDepositedDatasetController(base.FunctionalTestBase):

    ACTIONS = [
        'approve',
        'assign',
        'request_changes',
        'request_review',
        'reject',
        'submit',
        'withdraw',
    ]

    # Config

    def setup(self):
        super(TestDepositedDatasetController, self).setup()

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.depadmin = core_factories.User(name='depadmin', id='depadmin')
        self.curator = core_factories.User(name='curator', id='curator')
        self.creator = core_factories.User(name='creator', id='creator')
        self.depositor = core_factories.User(name='depositor', id='depositor')

        # Containers
        self.deposit = factories.DataContainer(
            users=[
                {'name': 'curator', 'capacity': 'editor'},
                {'name': 'depadmin', 'capacity': 'admin'},
            ],
            name='data-deposit',
            id='data-deposit'
        )
        self.target = factories.DataContainer(
            name='data-target',
            id='data-target'
        )

        # Dataset
        self.dataset = factories.DepositedDataset(
            name='dataset',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=self.creator)

    # Helpers

    def patch_dataset(self, patch):
        dataset = self.dataset.copy()
        dataset.update(patch)
        self.dataset = core_helpers.call_action(
            'package_update', {'user': 'sysadmin'}, **dataset)

    def make_request(self, action, dataset_id=None, user=None, **kwargs):
        url = '/deposited-dataset/%s/%s' % (dataset_id or self.dataset['id'], action)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url=url, extra_environ=env, **kwargs)
        if not dataset_id:
            try:
                self.dataset = core_helpers.call_action(
                    'package_show', {'user': 'sysadmin'}, id=self.dataset['id'])
            except toolkit.ObjectNotFound:
                self.dataset = None
        return resp

    # General

    def test_all_actions_anonimous(self):
        for action in self.ACTIONS:
            self.make_request(action, status=403)

    def test_all_actions_bad_dataset_id(self):
        for action in self.ACTIONS:
            self.make_request(action, dataset_id='bad-id', status=403)

    def test_all_actions_bad_dataset_type(self):
        factories.Dataset(name='regular', owner_org='data-target', user=self.creator)
        for action in self.ACTIONS:
            self.make_request(action, dataset_id='regular', user='sysadmin', status=403)

    # Approve (draft)

    def test_approve_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_approve_draft_not_granted, user

    def check_approve_draft_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'unit_of_measurement': 'individual',
            'keywords': ['shelter', 'health'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=403)

    # Approve (submitted)

    def test_approve_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_approve_submitted, user

    def check_approve_submitted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['shelter', 'health'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=302)
        assert_equals(self.dataset['type'], 'dataset')

    def test_approve_submitted_not_valid(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_approve_submitted_not_valid, user

    def check_approve_submitted_not_valid(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=403)

    def test_approve_submitted_not_granted(self):
        for user in ['creator', 'depositor']:
            yield self.check_approve_submitted_not_granted, user

    def check_approve_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=403)

    # Approve (review)

    def test_approve_review(self):
        for user in ['creator']:
            yield self.check_approve_review, user

    def check_approve_review(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
            'unit_of_measurement': 'individual',
            'keywords': ['shelter', 'health'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=302)
        assert_equals(self.dataset['type'], 'dataset')
        assert_equals(self.dataset['owner_org'], 'data-target')

    def test_approve_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'depositor']:
            yield self.check_approve_review_not_granted, user

    def check_approve_review_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=403)

    # Assign (draft)

    def test_assign_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_assign_draft_not_granted, user

    def check_assign_draft_not_granted(self, user):

        # Request changes
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=user, params=params, status=403)

    # Assign (submitted)

    def test_assign_submitted(self):
        for user in ['sysadmin', 'depadmin']:
            yield self.check_assign_submitted, user

    def check_assign_submitted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=user, params=params, status=302)
        assert_equals(self.dataset['curator_id'], self.curator['id'])

    def test_assign_submitted_no_one(self):
        for user in ['sysadmin', 'depadmin']:
            yield self.check_assign_submitted_no_one, user

    def check_assign_submitted_no_one(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': ''}
        self.make_request('assign', user=user, params=params, status=302)
        assert_equals(self.dataset.get('curator_id'), None)

    # TODO: it breaks sessions for all following tests
    #  def test_assign_submitted_bad_curator_id(self):
        #  for user in ['sysadmin', 'depadmin']:
            #  yield self.check_assign_submitted_bad_curator_id, user

    def check_assign_submitted_bad_curator_id(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.depositor['id']}
        self.make_request('assign', user=user, params=params, status=403)

    def test_assign_submitted_not_granted(self):
        for user in ['curator', 'creator', 'depositor']:
            yield self.check_assign_submitted_not_granted, user

    def check_assign_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=user, params=params, status=403)

    # Assign (review)

    def test_assign_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_assign_review_not_granted, user

    def check_assign_review_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request changes
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=user, params=params, status=403)

    # Request Changes (draft)

    def test_request_changes_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_request_changes_draft_not_granted, user

    def check_request_changes_draft_not_granted(self, user):

        # Request changes
        self.make_request('request_changes', user=user, status=403)

    # Request Changes (submitted)

    def test_request_changes_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_request_changes_submitted, user

    def check_request_changes_submitted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'draft')

    def test_request_changes_submitted_not_granted(self):
        for user in ['creator', 'depositor']:
            yield self.check_request_changes_submitted_not_granted, user

    def check_request_changes_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=403)

    # Request Changes (review)

    def test_request_changes_review(self):
        for user in ['creator']:
            yield self.check_request_changes_review, user

    def check_request_changes_review(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
            'unit_of_measurement': 'individual',
            'keywords': ['shelter', 'health'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'submitted')

    def test_request_changes_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'depositor']:
            yield self.check_request_changes_review_not_granted, user

    def check_request_changes_review_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=403)

    # Request Review (draft)

    def test_request_review_draft(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_request_review_draft, user

    def check_request_review_draft(self, user):

        # Prepare dataset
        self.patch_dataset({
            'unit_of_measurement': 'individual',
            'keywords': ['shelter', 'health'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
        })

        # Request review
        self.make_request('request_review', user=user, status=403)

    # Request Review (submitted)

    def test_request_review_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_request_review_submitted, user

    def check_request_review_submitted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['shelter', 'health'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
        })

        # Request review
        self.make_request('request_review', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'review')

    def test_request_review_submitted_not_valid(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_request_review_submitted_not_valid, user

    def check_request_review_submitted_not_valid(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request review
        self.make_request('request_review', user=user, status=403)

    def test_request_review_submitted_not_granted(self):
        for user in ['creator', 'depositor']:
            yield self.check_request_review_submitted_not_granted, user

    def check_request_review_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request review
        self.make_request('request_review', user=user, status=403)

    # Request Review (review)

    def test_request_review_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_request_review_review_not_granted, user

    def check_request_review_review_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request review
        self.make_request('request_review', user=user, status=403)

    # Reject (draft)

    def test_reject_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_reject_draft_not_granted, user

    def check_reject_draft_not_granted(self, user):

        # Reject dataset
        self.make_request('reject', user=user, status=403)

    # Reject (submitted)

    def test_reject_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_reject_submitted, user

    def check_reject_submitted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Reject dataset
        self.make_request('reject', user=user, status=302)
        assert_equals(self.dataset, None)

    def test_reject_submitted_not_granted(self):
        for user in ['creator', 'depositor']:
            yield self.check_reject_submitted_not_granted, user

    def check_reject_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Reject dataset
        self.make_request('reject', user=user, status=403)

    # Reject (review)

    def test_reject_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_reject_review_not_granted, user

    def check_reject_review_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Reject dataset
        self.make_request('reject', user=user, status=403)

    # Submit (draft)

    def test_submit_draft(self):
        for user in ['creator']:
            yield self.check_submit_draft, user

    def check_submit_draft(self, user):

        # Submit dataset
        self.make_request('submit', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'submitted')

    def test_submit_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'depositor']:
            yield self.check_submit_draft_not_granted, user

    def check_submit_draft_not_granted(self, user):

        # Submit dataset
        self.make_request('submit', user=user, status=403)

    # Submit (submitted)

    def test_submit_submitted_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_submit_submitted_not_granted, user

    def check_submit_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Submit dataset
        self.make_request('submit', user=user, status=403)

    # Submit (review)

    def test_submit_reviw_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_submit_reviw_not_granted, user

    def check_submit_reviw_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Submit dataset
        self.make_request('submit', user=user, status=403)

    # Withdraw (draft)

    def test_withdraw_draft(self):
        for user in ['creator']:
            yield self.check_withdraw_draft, user

    def check_withdraw_draft(self, user):

        # Withdraw dataset
        self.make_request('withdraw', user=user, status=302)
        assert_equals(self.dataset, None)

    def test_withdraw_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'depositor']:
            yield self.check_withdraw_draft_not_granted, user

    def check_withdraw_draft_not_granted(self, user):

        # Withdraw dataset
        self.make_request('withdraw', user=user, status=403)

    # Withdraw (submitted)

    def test_withdraw_submitted_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_withdraw_submitted, user

    def check_withdraw_submitted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Withdraw dataset
        self.make_request('withdraw', user=user, status=403)

    # Withdraw (review)

    def test_withdraw_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_withdraw_review, user

    def check_withdraw_review(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Withdraw dataset
        self.make_request('withdraw', user=user, status=403)
