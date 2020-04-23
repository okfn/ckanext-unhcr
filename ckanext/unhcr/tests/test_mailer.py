from datetime import datetime, timedelta
import ckan.model as model
from ckan.lib.jinja_extensions import regularise_html
import ckan.lib.search as search
from ckan.plugins import toolkit
from ckan.tests import factories as core_factories
from ckanext.unhcr.tests import base, factories
from ckanext.unhcr import mailer


class TestSummaryMailer(base.FunctionalTestBase):

    # General

    def setup(self):
        super(TestSummaryMailer, self).setup()

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')

    def test_email_body(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        factories.Dataset(
            name='new-dataset',
            title='New Dataset',
        )
        factories.Dataset(
            name='new-deposit',
            title='New Deposit',
            type='deposited-dataset',
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            curation_state='submitted',
        )
        factories.Dataset(
            name='awaiting-review',
            title='Awaiting Review',
            type='deposited-dataset',
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            curation_state='review',
        )
        old_dataset = factories.Dataset(
            name='old-dataset',
            title='Old Dataset',
        )
        # This is a little bit messy.
        # We can't set the `metadata_created` property via a factory or an
        # action and the default is set in postgres so freezegun doesn't help.
        # So we will update the value directly using SQLAlchemy:
        model.Session.query(model.Package).filter_by(id=old_dataset['id']).update(
            { "metadata_created": datetime.now() - timedelta(days=8) }
        )
        model.Session.commit()
        # ..and then refresh the search index
        # so that the record is up-to-date when we query solr
        search.rebuild(package_id=old_dataset['id'])

        expected_values = [
            '''
            <h1>New datasets (1)</h1>
            <ul> <li> <a href="{}">New Dataset</a> </li> </ul>'''.format(
                toolkit.url_for('dataset_read', id='new-dataset', qualified=True)
            ),

            '''
            <h2>New deposited datasets (1)</h2>
            <ul> <li> <a href="{}">New Deposit</a> </li> </ul>'''.format(
                toolkit.url_for('dataset_read', id='new-deposit', qualified=True)
            ),

            '''
            <h2>Datasets awaiting review (1)</h2>
            <ul> <li> <a href="{}">Awaiting Review</a> </li> </ul>'''.format(
                toolkit.url_for('dataset_read', id='awaiting-review', qualified=True)
            ),
        ]

        email = mailer.compose_summary_email_body(self.sysadmin)
        regularised_body = regularise_html(email['body'])

        assert 3 == email['total_events']
        for ev in expected_values:
            assert regularise_html(ev) in regularised_body
        assert 'Old Dataset' not in regularised_body
        assert (
            toolkit.url_for("dataset_read", id="old-dataset", qualified=True)
            not in regularised_body
        )

    def test_email_recipients(self):
        user1 = core_factories.User(name='user1', id='user1')
        curator = core_factories.User(name='curator', id='curator')
        factories.DataContainer(
            users=[
                {'name': 'curator', 'capacity': 'editor'},
            ],
            name='data-deposit',
            id='data-deposit'
        )

        recipients = mailer.get_summary_email_recipients()
        recipient_ids = [r['name'] for r in recipients]

        assert len(recipient_ids) == 2
        assert curator['name'] in recipient_ids
        assert self.sysadmin['name'] in recipient_ids
        assert user1['name'] not in recipient_ids


class TestCollaborationMailer(base.FunctionalTestBase):

    # General

    def setup(self):
        super(TestCollaborationMailer, self).setup()

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')

    def test_email_body(self):
        user1 = core_factories.User(name='user1', id='user1')
        dataset1 = factories.Dataset(
            name='new-dataset',
            title='New Dataset',
        )

        user_message = 'I can haz access?\nkthxbye'
        email_body = mailer.compose_request_access_email_body(self.sysadmin, dataset1, user1, user_message)
        regularised_body = regularise_html(email_body)
        expected = regularise_html(
            'User <a href="{user_link}">Mr. Test User</a> has requested access to download <a href="{dataset_link}">New Dataset</a>'.format(
                user_link=toolkit.url_for('user.read', id=user1['id'], qualified=True),
                dataset_link=toolkit.url_for('dataset_read', id=dataset1['name'], qualified=True),
            )
        )

        assert expected in regularised_body
        assert '<p>I can haz access?<br> kthxbye</p>' in regularised_body

    def test_email_recipients(self):
        editor = core_factories.User()
        admin = core_factories.User()
        external = core_factories.User()
        container = factories.DataContainer(
            users=[
                {'name': editor['name'], 'capacity': 'editor'},
                {'name': admin['name'], 'capacity': 'admin'},
            ],
            name='container1',
            id='container1'
        )
        dataset1 = factories.Dataset(
            name='new-dataset',
            title='New Dataset',
            owner_org=container['id'],
        )
        recipients = mailer.get_request_access_email_recipients(dataset1)

        assert len(recipients) == 1
        assert admin['name'] == recipients[0]['name']
