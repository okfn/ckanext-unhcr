# -*- coding: utf-8 -*-

import pytest
import mock
from datetime import datetime, timedelta
import ckan.model as model
from ckan.lib.jinja_extensions import regularise_html
import ckan.lib.search as search
from ckan.plugins import toolkit
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories
from ckanext.unhcr import mailer


@pytest.mark.usefixtures('clean_db', 'clean_index', 'unhcr_migrate')
class TestSummaryMailer(object):

    # General

    def setup(self):
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')

    def test_email_body(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        org = factories.DataContainer(name='test-org', title='Test Org')
        factories.Dataset(
            name='new-dataset',
            title='New Dataset',
            owner_org=org['id'],
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
            owner_org=org['id'],
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
            <h2> <a href="{org}">Test Org</a> (1) </h2>
            <ul> <li> <a href="{ds}">New Dataset</a> in <a href="{org}">Test Org</a> </li> </ul>'''.format(
                ds=toolkit.url_for('dataset_read', id='new-dataset', qualified=True),
                org=toolkit.url_for('data-container_read', id='test-org', qualified=True)
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

    def test_email_hierarchy(self):
        africa = factories.DataContainer(name='africa', title='Africa')
        europe = factories.DataContainer(name='europe', title='Europe')
        americas = factories.DataContainer(name='americas', title='Americas')

        central_africa = factories.DataContainer(
            name='central-africa',
            title='Central Africa and the Great Lakes',
            groups=[{'name': africa['name']}],
        )
        eastern_europe = factories.DataContainer(
            name='eastern-europe',
            title='Eastern Europe',
            groups=[{'name': europe['name']}],
        )

        burundi = factories.DataContainer(
            name='burundi',
            title='Burundi',
            groups=[{'name': central_africa['name']}],
        )
        belarus = factories.DataContainer(
            name='belarus',
            title='Belarus',
            groups=[{'name': eastern_europe['name']}],
        )

        factories.Dataset(
            name='africa-dataset1',
            title='Africa Dataset 1',
            owner_org=africa['id'],
        )
        factories.Dataset(
            name='central-africa-dataset1',
            title='Central Africa Dataset 1',
            owner_org=central_africa['id'],
        )
        factories.Dataset(
            name='burundi-dataset1',
            title='Burundi Dataset 1',
            owner_org=burundi['id'],
        )

        factories.Dataset(
            name='belarus-dataset1',
            title='Belarus Dataset 1',
            owner_org=belarus['id'],
        )

        email = mailer.compose_summary_email_body(self.sysadmin)
        regularised_body = regularise_html(email['body'])

        expected_values = [
            '''
            <h1>New datasets (4)</h1>
            ''',

            '''
            <h2> <a href="{}">Africa</a> (3) </h2>
            '''.format(toolkit.url_for('data-container_read', id='africa', qualified=True)),

            '''
            <li> <a href="{dataset}">Burundi Dataset 1</a> in <a href="{container}">Burundi</a> </li>
            '''.format(
                dataset=toolkit.url_for('dataset_read', id='burundi-dataset1', qualified=True),
                container=toolkit.url_for('data-container_read', id='burundi', qualified=True),
            ),

            '''
            <li> <a href="{dataset}">Central Africa Dataset 1</a> in <a href="{container}">Central Africa and the Great Lakes</a> </li>
            '''.format(
                dataset=toolkit.url_for('dataset_read', id='central-africa-dataset1', qualified=True),
                container=toolkit.url_for('data-container_read', id='central-africa', qualified=True),
            ),

            '''
            <li> <a href="{dataset}">Africa Dataset 1</a> in <a href="{container}">Africa</a> </li>
            '''.format(
                dataset=toolkit.url_for('dataset_read', id='africa-dataset1', qualified=True),
                container=toolkit.url_for('data-container_read', id='africa', qualified=True),
            ),

            '''
            <h2> <a href="{root}">Europe</a> (1) </h2>
            <ul>
              <li> <a href="{dataset}">Belarus Dataset 1</a> in <a href="{container}">Belarus</a> </li>
            </ul>
            '''.format(
                root=toolkit.url_for('data-container_read', id='europe', qualified=True),
                dataset=toolkit.url_for('dataset_read', id='belarus-dataset1', qualified=True),
                container=toolkit.url_for('data-container_read', id='belarus', qualified=True),
            ),
        ]

        assert 4 == email['total_events']
        for ev in expected_values:
            assert regularise_html(ev) in regularised_body
        assert 'Americas' not in regularised_body
        assert (
            toolkit.url_for('data-container_read', id='americas', qualified=True)
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


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestAccessRequestMailer(object):

    # General

    def setup(self):
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')

    def test_dataset_request_access_body(self):
        user1 = core_factories.User(name='user1', id='user1')
        dataset1 = factories.Dataset(
            name='new-dataset',
            title='New Dataset',
        )

        user_message = 'I can haz access?\nkthxbye'
        email_body = mailer.compose_request_access_email_body(
            'dataset', self.sysadmin, dataset1, user1, user_message
        )
        regularised_body = regularise_html(email_body)
        expected = regularise_html(
            'User <a href="{user_link}">Mr. Test User</a> has requested access to download <a href="{dataset_link}">New Dataset</a>'.format(
                user_link=toolkit.url_for('user.read', id=user1['id'], qualified=True),
                dataset_link=toolkit.url_for('dataset_read', id=dataset1['name'], qualified=True),
            )
        )

        assert expected in regularised_body
        assert '<p>I can haz access?<br> kthxbye</p>' in regularised_body

    def test_container_request_access_body(self):
        user1 = core_factories.User(name='user1', id='user1')
        container1 = factories.DataContainer(
            name='new-container',
            title='New Container',
        )

        user_message = 'I can haz access?\nkthxbye'
        email_body = mailer.compose_request_access_email_body(
            'container', self.sysadmin, container1, user1, user_message
        )
        regularised_body = regularise_html(email_body)
        expected = regularise_html(
            'User <a href="{user_link}">Mr. Test User</a> has requested access to <a href="{container_link}">New Container</a>'.format(
                user_link=toolkit.url_for('user.read', id=user1['id'], qualified=True),
                container_link=toolkit.url_for('data-container_read', id=container1['name'], qualified=True),
            )
        )

        assert expected in regularised_body
        assert '<p>I can haz access?<br> kthxbye</p>' in regularised_body

    def test_user_request_access_body(self):
        user1 = core_factories.User(name='user1', id='user1')

        user_message = 'I can haz access?\nkthxbye'
        email_body = mailer.compose_request_access_email_body(
            'user', self.sysadmin, user1, user1, user_message
        )
        regularised_body = regularise_html(email_body)
        expected = regularise_html(
            'External user <a href="{user_link}">Mr. Test User</a> has requested access to deposit datasets.'.format(
                user_link=toolkit.url_for('user.read', id=user1['id'], qualified=True),
            )
        )

        assert expected in regularised_body
        assert '<p>I can haz access?<br> kthxbye</p>' in regularised_body

    def test_recipients_with_org_admins(self):
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
        dataset_recipients = mailer.get_dataset_request_access_email_recipients(dataset1)
        container_recipients = mailer.get_container_request_access_email_recipients(container)

        assert dataset_recipients == container_recipients
        assert len(container_recipients) == 1
        assert admin['name'] == container_recipients[0]['name']

    def test_recipients_no_org_admins(self):
        editor = core_factories.User()
        external = core_factories.User()
        container = factories.DataContainer(
            users=[
                {'name': editor['name'], 'capacity': 'editor'},
            ],
            name='container1',
            id='container1'
        )
        dataset1 = factories.Dataset(
            name='new-dataset',
            title='New Dataset',
            owner_org=container['id'],
        )
        dataset_recipients = mailer.get_dataset_request_access_email_recipients(dataset1)
        container_recipients = mailer.get_container_request_access_email_recipients(container)

        assert dataset_recipients == container_recipients
        assert len(container_recipients) == 1
        assert self.sysadmin['name'] == container_recipients[0]['name']

    def test_request_rejected_email_body_dataset(self):
        user1 = core_factories.User(name='user1', id='user1')
        dataset1 = factories.Dataset(title='Test Dataset 1')

        message = 'Nope\nNot today thank you'
        email_body = mailer.compose_request_rejected_email_body('dataset', user1, dataset1, message)
        regularised_body = regularise_html(email_body)

        assert 'Your request to access <strong>Test Dataset 1</strong> has been rejected.' in regularised_body
        assert '<p>Nope<br> Not today thank you</p>' in regularised_body

    def test_request_rejected_email_body_container(self):
        user1 = core_factories.User(name='user1', id='user1')
        container1 = factories.DataContainer(title='Test Organization 1')

        message = 'Nope\nNot today thank you'
        email_body = mailer.compose_request_rejected_email_body('container', user1, container1, message)
        regularised_body = regularise_html(email_body)

        assert 'Your request to access <strong>Test Organization 1</strong> has been rejected.' in regularised_body
        assert '<p>Nope<br> Not today thank you</p>' in regularised_body

    def test_request_rejected_email_body_user(self):
        user1 = core_factories.User(name='user1', id='user1')

        message = 'Nope\nNot today thank you'
        email_body = mailer.compose_request_rejected_email_body('user', user1, user1, message)
        regularised_body = regularise_html(email_body)

        assert 'Your request for a RIDL user account has been rejected.' in regularised_body
        assert '<p>Nope<br> Not today thank you</p>' in regularised_body

    def test_account_approved_email_body(self):
        user1 = core_factories.User(name='user1', id='user1')
        email_body = mailer.compose_account_approved_email_body(user1)
        regularised_body = regularise_html(email_body)

        assert 'Your request for a RIDL user account has been approved by an administrator.' in regularised_body

    def test_get_user_account_request_access_email_recipients(self):
        users = [
            core_factories.User(),
            core_factories.User(),
            core_factories.User(),
            core_factories.User(),
        ]
        containers = [
            factories.DataContainer(
                users=[
                    {'name': users[0]['name'], 'capacity': 'admin'},
                    {'name': users[1]['name'], 'capacity': 'admin'},
                    {'name': users[2]['name'], 'capacity': 'editor'},
                ]
            ),
            factories.DataContainer(
                users=[
                    {'name': users[0]['name'], 'capacity': 'admin'},
                    {'name': users[2]['name'], 'capacity': 'editor'},
                ]
            ),
            factories.DataContainer(
                users=[
                    {'name': users[0]['name'], 'capacity': 'admin'},
                ]
            ),
            factories.DataContainer(
                users=[
                    {'name': users[3]['name'], 'capacity': 'admin'},
                ]
            ),
        ]
        recipients = mailer.get_user_account_request_access_email_recipients([
            containers[0]['id'], containers[1]['id'], containers[2]['id']
        ])

        recipient_ids = [r['id'] for r in recipients]

        assert len(recipient_ids) == 3

        # no duplicates
        assert len(recipient_ids) == len(list(set(recipient_ids)))

        # users[0] and users[1] are admins of >=1 container
        assert users[0]['id'] in recipient_ids
        assert users[1]['id'] in recipient_ids

        # users[2] isn't an admin of any container
        assert users[2]['id'] not in recipient_ids

        # users[3] isn't an admin of any container we specified
        assert users[2]['id'] not in recipient_ids

        # we should always mail sysadmin
        assert self.sysadmin['id'] in recipient_ids


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestInfectedFileMailer(object):

    def test_email_body(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        email_body = mailer.compose_infected_file_email_body(
            sysadmin,
            'infected resource',
            'package-id',
            'resource-id',
            '/tmp/tmpmmy4xf83: Win.Test.EICAR_HDB-1 FOUND\n\n----------- SCAN SUMMARY -----------\nKnown viruses: 8945582\nEngine version: 0.102.4\nScanned directories: 0\nScanned files: 1\nInfected files: 1\nData scanned: 0.00 MB\nData read: 0.00 MB (ratio 0.00:1)\nTime: 27.025 sec (0 m 27 s)\n',
        )
        regularised_body = regularise_html(email_body)

        resource_link = toolkit.url_for(
            controller='package',
            action='resource_read',
            id='package-id',
            resource_id='resource-id',
            qualified=True
        )
        assert '<a href="{}">infected resource</a>'.format(resource_link) in regularised_body
        assert 'scanned and found to be infected.' in regularised_body
        assert 'Win.Test.EICAR_HDB-1 FOUND' in regularised_body


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestCollaboratorsMailer(object):

    @mock.patch('ckanext.unhcr.mailer.core_mailer.mail_user')
    def test_email_notification_create(self, mock_mail_user):
        dataset = factories.Dataset()
        user = core_factories.User()
        capacity = 'editor'

        mailer.mail_notification_to_collaborator(
            dataset['id'], user['id'], capacity, 'create')

        assert mock_mail_user.call_count == 1

    @mock.patch('ckanext.unhcr.mailer.core_mailer.mail_user')
    def test_email_notification_delete(self, mock_mail_user):
        dataset = factories.Dataset()
        user = core_factories.User()
        capacity = 'editor'

        mailer.mail_notification_to_collaborator(
            dataset['id'], user['id'], capacity, 'delete')

        assert mock_mail_user.call_count == 1

    # TODO: tests for body function

    def test_subject_unicode(self):
        dataset = factories.Dataset(title=u'réfugiés')
        subject = mailer._compose_collaborator_email_subj(model.Package.get(dataset['id']))
        assert u'réfugiés' in subject
