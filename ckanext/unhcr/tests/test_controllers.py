import nose
import mock
from nose.plugins.attrib import attr
from ckan.lib.helpers import url_for
from ckan.logic import NotFound
from ckan.plugins import toolkit
from nose.tools import assert_raises, assert_equals, nottest
from ckan.tests import helpers as core_helpers, factories as core_factories
from ckanext.unhcr.tests import base, factories

assert_in = core_helpers.assert_in
assert_not_in = core_helpers.assert_not_in

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
        self.editor = core_factories.User(name='editor', id='editor')

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
            id='data-target',
            users=[
                {'name': 'editor', 'capacity': 'editor'},
            ],

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

    def assert_mail(self, mail, users, subject, texts):
        for index, user in enumerate(users):
            assert_equals(mail.call_args_list[index][0][0], user)
            assert_equals(mail.call_args_list[index][0][1], subject)
            for text in texts:
                assert_in(text, mail.call_args_list[index][0][2])

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
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Approve dataset
        # TODO: follow redirect and check for "action is not available"
        self.make_request('approve', user=user, status=403 if user == 'depositor' else 302)

    # Approve (submitted)

    def test_approve_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_approve_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_approve_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=302)
        assert_equals(self.dataset['type'], 'dataset')
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been approved'],
        )

    def test_approve_submitted_final_review_requested(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_approve_submitted_final_review_requested, user

    def check_approve_submitted_final_review_requested(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Approve dataset
        # TODO: follow redirect and check for "action is not available"
        self.make_request('approve', user=user, status=302)

    def test_approve_submitted_not_valid(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_approve_submitted_not_valid, user

    def check_approve_submitted_not_valid(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=302)

    def test_approve_submitted_not_granted(self):
        for user in ['creator', 'depositor']:
            yield self.check_approve_submitted_not_granted, user

    def check_approve_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Approve dataset
        # TODO: follow redirect and check for "action is not available"
        self.make_request('approve', user=user, status=403 if user == 'depositor' else 302)

    # Approve (review)

    def test_approve_review_without_curator(self):
        for user in ['creator']:
            yield self.check_approve_review_without_curator, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_approve_review_without_curator(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=302)
        assert_equals(self.dataset['type'], 'dataset')
        assert_equals(self.dataset['owner_org'], 'data-target')
        mail.assert_not_called()

    def test_approve_review_with_curator(self):
        for user in ['creator']:
            yield self.check_approve_review_with_curator, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_approve_review_with_curator(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curator_id': 'curator',
            'curation_state': 'review',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=302)
        assert_equals(self.dataset['type'], 'dataset')
        assert_equals(self.dataset['owner_org'], 'data-target')
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been approved'],
        )

    def test_approve_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'depositor']:
            yield self.check_approve_review_not_granted, user

    def check_approve_review_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Approve dataset
        # TODO: follow redirect and check for "action is not available"
        self.make_request('approve', user=user, status=403 if user == 'depositor' else 302)

    # Assign (draft)

    def test_assign_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_assign_draft_not_granted, user

    def check_assign_draft_not_granted(self, user):

        # Request changes
        params = {'curator_id': self.curator['id']}
        # TODO: follow redirect and check for "action is not available"
        self.make_request('assign', user=user, params=params, status=403 if user == 'depositor' else 302)

    # Assign (submitted)

    def test_assign_submitted(self):
        for user in ['sysadmin', 'depadmin']:
            yield self.check_assign_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=user, params=params, status=302)
        assert_equals(self.dataset['curator_id'], self.curator['id'])
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['A new dataset has been assigned to you for curation'],
        )

    def test_assign_submitted_remove(self):
        for user in ['sysadmin', 'depadmin']:
            yield self.check_assign_submitted_remove, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted_remove(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curator_id': 'curator',
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': ''}
        self.make_request('assign', user=user, params=params, status=302)
        assert_equals(self.dataset.get('curator_id'), None)
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['You have been removed as Curator of the following dataset'],
        )

    def test_assign_submitted_remove_not_assigned(self):
        for user in ['sysadmin', 'depadmin']:
            yield self.check_assign_submitted_remove_not_assigned, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted_remove_not_assigned(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': ''}
        self.make_request('assign', user=user, params=params, status=302)
        assert_equals(self.dataset.get('curator_id'), None)
        mail.assert_not_called()

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
        # TODO: follow redirect and check for "action is not available"
        self.make_request('assign', user=user, params=params, status=403 if user == 'depositor' else 302)

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
        # TODO: follow redirect and check for "action is not available"
        self.make_request('assign', user=user, params=params, status=403 if user == 'depositor' else 302)

    # Request Changes (draft)

    def test_request_changes_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_request_changes_draft_not_granted, user

    def check_request_changes_draft_not_granted(self, user):

        # Request changes
        # TODO: follow redirect and check for "action is not available"
        self.make_request('request_changes', user=user, status=403 if user == 'depositor' else 302)

    # Request Changes (submitted)

    def test_request_changes_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_request_changes_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_request_changes_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'draft')
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['The Reviewer has requested changes on the following dataset'],
        )

    def test_request_changes_submitted_not_granted(self):
        for user in ['creator', 'depositor']:
            yield self.check_request_changes_submitted_not_granted, user

    def check_request_changes_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request changes
        # TODO: follow redirect and check for "action is not available"
        self.make_request('request_changes', user=user, status=403 if user == 'depositor' else 302)

    # Request Changes (review)

    def test_request_changes_review(self):
        for user in ['creator']:
            yield self.check_request_changes_review, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_request_changes_review(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curator_id': 'curator',
            'curation_state': 'review',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'submitted')
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['The Reviewer has requested changes on the following dataset'],
        )

    def test_request_changes_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'depositor']:
            yield self.check_request_changes_review_not_granted, user

    def check_request_changes_review_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request changes
        # TODO: follow redirect and check for "action is not available"
        self.make_request('request_changes', user=user, status=403 if user == 'depositor' else 302)

    # Request Review (draft)

    def test_request_review_draft(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_request_review_draft, user

    def check_request_review_draft(self, user):

        # Prepare dataset
        self.patch_dataset({
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Request review
        # TODO: follow redirect and check for "action is not available"
        self.make_request('request_review', user=user, status=403 if user == 'depositor' else 302)

    # Request Review (submitted)

    def test_request_review_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_request_review_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_request_review_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Request review
        self.make_request('request_review', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'review')
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['As Depositor of this dataset, the Curator assigned to it has requested your final review before publication'],
        )

    def test_request_review_submitted_not_final_review_requested(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_request_review_submitted_not_final_review_requested, user

    def check_request_review_submitted_not_final_review_requested(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Request review
        # TODO: follow redirect and check for "action is not available"
        self.make_request('request_review', user=user, status=302)

    def test_request_review_submitted_not_valid(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_request_review_submitted_not_valid, user

    def check_request_review_submitted_not_valid(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Request review
        # TODO: follow redirect and check for "action is not available"
        self.make_request('request_review', user=user, status=302)

    def test_request_review_submitted_not_granted(self):
        for user in ['creator', 'depositor']:
            yield self.check_request_review_submitted_not_granted, user

    def check_request_review_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Request review
        # TODO: follow redirect and check for "action is not available"
        self.make_request('request_review', user=user, status=403 if user == 'depositor' else 302)

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
        # TODO: follow redirect and check for "action is not available"
        self.make_request('request_review', user=user, status=403 if user == 'depositor' else 302)

    # Reject (draft)

    def test_reject_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'depositor']:
            yield self.check_reject_draft_not_granted, user

    def check_reject_draft_not_granted(self, user):

        # Reject dataset
        # TODO: follow redirect and check for "action is not available"
        self.make_request('reject', user=user, status=403 if user == 'depositor' else 302)

    # Reject (submitted)

    def test_reject_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator']:
            yield self.check_reject_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_reject_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Reject dataset
        self.make_request('reject', user=user, status=302)
        assert_equals(self.dataset['state'], 'deleted')
        assert_in('-rejected-', self.dataset['name'])
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been rejected'],
        )

    def test_reject_submitted_not_granted(self):
        for user in ['creator', 'depositor']:
            yield self.check_reject_submitted_not_granted, user

    def check_reject_submitted_not_granted(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Reject dataset
        # TODO: follow redirect and check for "action is not available"
        self.make_request('reject', user=user, status=403 if user == 'depositor' else 302)

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
        # TODO: follow redirect and check for "action is not available"
        self.make_request('reject', user=user, status=403 if user == 'depositor' else 302)

    # Submit (draft)

    def test_submit_draft(self):
        for user in ['creator']:
            yield self.check_submit_draft, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_submit_draft(self, user, mail):

        # Submit dataset
        self.make_request('submit', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'submitted')
        self.assert_mail(mail,
            users=['depadmin', 'curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['A new dataset has been submitted for curation by %s' % self.creator['display_name']],
        )

    def test_submit_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'depositor']:
            yield self.check_submit_draft_not_granted, user

    def check_submit_draft_not_granted(self, user):

        # Submit dataset
        # TODO: follow redirect and check for "action is not available"
        self.make_request('submit', user=user, status=403 if user == 'depositor' else 302)

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
        # TODO: follow redirect and check for "action is not available"
        self.make_request('submit', user=user, status=403 if user == 'depositor' else 302)

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
        # TODO: follow redirect and check for "action is not available"
        self.make_request('submit', user=user, status=403 if user == 'depositor' else 302)

    # Withdraw (draft)

    def test_withdraw_draft(self):
        for user in ['creator']:
            yield self.check_withdraw_draft, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_withdraw_draft(self, user, mail):

        # Withdraw dataset
        self.make_request('withdraw', user=user, status=302)
        assert_equals(self.dataset['state'], 'deleted')
        assert_in('-withdrawn-', self.dataset['name'])
        self.assert_mail(mail,
            users=['depadmin', 'curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been withdrawn from curation by %s' % self.creator['display_name']],
        )

    def test_withdraw_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'depositor']:
            yield self.check_withdraw_draft_not_granted, user

    def check_withdraw_draft_not_granted(self, user):

        # Withdraw dataset
        # TODO: follow redirect and check for "action is not available"
        self.make_request('withdraw', user=user, status=403 if user == 'depositor' else 302)

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
        # TODO: follow redirect and check for "action is not available"
        self.make_request('withdraw', user=user, status=403 if user == 'depositor' else 302)

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
        # TODO: follow redirect and check for "action is not available"
        self.make_request('withdraw', user=user, status=403 if user == 'depositor' else 302)

    # Activities

    def _approve_dataset(self):
        self.patch_dataset({
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        self.make_request('approve', user='sysadmin', status=302)

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def test_activites_shown_on_deposited_dataset(self, mail):

        env = {'REMOTE_USER': self.creator['name'].encode('ascii')}
        resp = self.app.get(
            url=url_for('deposited-dataset_read', id=self.dataset['id']), extra_environ=env)
        assert_in('Curation Activity', resp.body)

    def test_activites_shown_on_normal_dataset(self):
        for user in ['sysadmin', 'editor']:
            yield self.check_activities_shown, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_activities_shown(self, user, mail):

        self._approve_dataset()

        env = {'REMOTE_USER': user.encode('ascii')}
        resp = self.app.get(
            url=url_for('dataset_read', id=self.dataset['id']), extra_environ=env)

        assert_in('Curation Activity', resp.body)

    def test_activites_not_shown_on_normal_dataset(self):

        for user in ['depositor', 'curator']:
            yield self.check_activities_not_shown, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_activities_not_shown(self, user, mail):

        self._approve_dataset()

        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(
            url=url_for('dataset_read', id=self.dataset['id']), extra_environ=env)

        assert_not_in('Curation Activity', resp.body)

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def test_activity_created_in_deposited_dataset(self, mail):


        self.make_request('submit', user=self.creator['name'], status=302)
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=self.depadmin['name'], params=params)

        env = {'REMOTE_USER': self.curator['name'].encode('ascii')}
        resp = self.app.get(
            url=url_for('deposited-dataset_curation_activity', dataset_id=self.dataset['name']), extra_environ=env)

        assert_in('deposited dataset', resp.body)
        assert_in('submitted dataset', resp.body)
        assert_in('assigned', resp.body)
        assert_in('as Curator', resp.body)


class TestExtendedPackageController(base.FunctionalTestBase):

    # Config

    def setup(self):
        super(TestExtendedPackageController, self).setup()

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.user1 = core_factories.User(name='user1', id='user1')
        self.user2 = core_factories.User(name='user2', id='user2')
        self.user3 = core_factories.User(name='user3', id='user3')

        # Containers
        self.container1 = factories.DataContainer(
            name='container1',
            id='container1',
            users=[
                {'name': 'user1', 'capacity': 'admin'},
            ],
        )
        self.container2 = factories.DataContainer(
            name='container2',
            id='container2',
            users=[
                {'name': 'user2', 'capacity': 'admin'},
            ],
        )

        # Datasets
        self.dataset1 = factories.Dataset(
            name='dataset1',
            owner_org='container1',
            data_collection_technique = 'f2f',
            sampling_procedure = 'nonprobability',
            operational_purpose_of_data = 'cartography',
            user=self.user1)

        # Resources
        self.resource1 = factories.Resource(
            name='resource1',
            package_id='dataset1',
            url_type='upload',
        )

    # Helpers

    def make_dataset_request(self, dataset_id=None, user=None, **kwargs):
        url = '/dataset/copy/%s' % dataset_id
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_resource_request(self, dataset_id=None, resource_id=None, user=None, **kwargs):
        url = '/dataset/%s/resource_copy/%s' % (dataset_id, resource_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url=url, extra_environ=env, **kwargs)
        return resp

    # Dataset

    def test_dataset_copy(self):
        resp = self.make_dataset_request(dataset_id='dataset1', user='user1')
        assert_in('action="/dataset/new"', resp.body)
        #  assert_in('dataset1-copy', resp.body)
        assert_in('f2f', resp.body)
        assert_in('nonprobability', resp.body)
        assert_in('cartography', resp.body)
        assert_in('Add Data', resp.body)
        assert_in('container1', resp.body)

    def test_dataset_copy_to_other_org(self):
        resp = self.make_dataset_request(dataset_id='dataset1', user='user2')
        assert_in('action="/dataset/new"', resp.body)
        #  assert_in('dataset1-copy', resp.body)
        assert_in('f2f', resp.body)
        assert_in('nonprobability', resp.body)
        assert_in('cartography', resp.body)
        assert_in('Add Data', resp.body)
        assert_not_in('container1', resp.body)

    def test_dataset_copy_no_orgs(self):
        resp = self.make_dataset_request(dataset_id='dataset1', user='user3', status=403)

    def test_dataset_copy_bad_dataset(self):
        resp = self.make_dataset_request(dataset_id='bad', user='user1', status=404)

    # Resource

    def test_resource_copy(self):
        resp = self.make_resource_request(
            dataset_id='dataset1', resource_id=self.resource1['id'], user='user1')
        assert_in('action="/dataset/new_resource/dataset1"', resp.body)
        assert_in('resource1 (copy)', resp.body)
        assert_in('anonymized_public', resp.body)
        assert_in('Add', resp.body)

    def test_resource_copy_no_access(self):
        resp = self.make_resource_request(
            dataset_id='dataset1', resource_id=self.resource1['id'], user='user2', status=403)

    def test_resource_copy_bad_resource(self):
        resp = self.make_resource_request(
            dataset_id='dataset1', resource_id='bad', user='user1', status=404)


class TestDataContainerController(base.FunctionalTestBase):

    # Config

    def setup(self):
        super(TestDataContainerController, self).setup()

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.user1 = core_factories.User(name='user1', id='user1')
        self.user2 = core_factories.User(name='user2', id='user2')
        self.user3 = core_factories.User(name='user3', id='user3')

        # Containers
        self.container1 = factories.DataContainer(
            name='container1',
            id='container1',
        )
        self.container2 = factories.DataContainer(
            name='container2',
            id='container2',
        )

    # Helpers

    def get_request(self, url, user=None, **kwargs):
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url, extra_environ=env, **kwargs)
        self.update_containers()
        return resp

    def post_request(self, url, data, user=None, **kwargs):
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.post(url, data, extra_environ=env, **kwargs)
        self.update_containers()
        return resp

    def update_containers(self):
        self.container1 = core_helpers.call_action(
            'organization_show', {'user': 'sysadmin'}, id='container1')
        self.container2 = core_helpers.call_action(
            'organization_show', {'user': 'sysadmin'}, id='container2')

    # General

    def test_membership(self):
        resp = self.get_request('/data-container/membership', user='sysadmin')
        assert_in('Manage Membership', resp.body)

    def test_membership_no_access(self):
        resp = self.get_request('/data-container/membership', user='user1', status=403)

    def test_membership_user(self):
        resp = self.get_request('/data-container/membership?username=user1', user='sysadmin')
        assert_in('Manage Membership', resp.body)
        assert_in('Add Containers', resp.body)
        assert_in('Current Containers', resp.body)

    # Add Containers

    def test_membership_add(self):
        data = {
            'username': 'user1',
            'contnames': 'container1',
            'role': 'editor',
        }
        resp = self.post_request('/data-container/membership_add', data, user='sysadmin')
        assert_equals(resp.status_int, 302)
        assert_equals(len(self.container1['users']), 2)
        #  assert_equals(self.container1['users'][0]['name'], 'default_test')
        assert_equals(self.container1['users'][0]['capacity'], 'admin')
        assert_equals(self.container1['users'][1]['name'], 'user1')
        assert_equals(self.container1['users'][1]['capacity'], 'editor')

    def test_membership_add_multiple_containers(self):
        data = {
            'username': 'user1',
            'contnames': ['container1', 'container2'],
            'role': 'editor',
        }
        resp = self.post_request('/data-container/membership_add', data, user='sysadmin')
        assert_equals(resp.status_int, 302)
        assert_equals(len(self.container1['users']), 2)
        #  assert_equals(self.container1['users'][0]['name'], 'default_test')
        assert_equals(self.container1['users'][0]['capacity'], 'admin')
        assert_equals(self.container1['users'][1]['name'], 'user1')
        assert_equals(self.container1['users'][1]['capacity'], 'editor')
        assert_equals(len(self.container2['users']), 2)
        #  assert_equals(self.container2['users'][0]['name'], 'default_test')
        assert_equals(self.container2['users'][0]['capacity'], 'admin')
        assert_equals(self.container2['users'][1]['name'], 'user1')
        assert_equals(self.container2['users'][1]['capacity'], 'editor')

    def test_membership_add_no_access(self):
        data = {
            'username': 'user1',
            'contnames': 'container1',
            'role': 'editor',
        }
        resp = self.post_request('/data-container/membership_add', data, user='user3', status=403)

    # Remove Container

    def test_membership_remove(self):
        self.test_membership_add()
        url = '/data-container/membership_remove?username=user1&contname=container1'
        resp = self.get_request(url, user='sysadmin')
        assert_equals(resp.status_int, 302)
        assert_equals(len(self.container1['users']), 1)
        #  assert_equals(self.container1['users'][0]['name'], 'default_test')
        assert_equals(self.container1['users'][0]['capacity'], 'admin')

    def test_membership_remove_no_access(self):
        url = '/data-container/membership_remove?username=default_test&contname=container1'
        resp = self.get_request(url, user='user3', status=403)
