# -*- coding: utf-8 -*-

import click

from ckan.plugins import toolkit
import ckan.model as model

from ckanext.unhcr.models import create_tables, TimeSeriesMetric
from ckanext.unhcr.mailer import (
    compose_summary_email_body,
    get_summary_email_recipients,
    mail_user_by_id
)


@click.group(short_help=u'UNHCR plugin management commands')
def unhcr():
    pass


@unhcr.command(
    u'init-db',
    short_help=u'Create UNHCR DB tables'
)
def init_db():
    create_tables()
    print(u'UNHCR tables initialized')


@unhcr.command(
    u'snapshot-metrics',
    short_help=u'Take a snapshot of time-series metrics'
)
def snapshot_metrics():
    context = { 'ignore_auth': True }

    data_dict = {
        'q': '*:*',
        'rows': 0,
        'include_private': True,
    }
    packages = toolkit.get_action('package_search')(
        context, dict(data_dict, fq='-type:deposited-dataset'))
    deposits = toolkit.get_action('package_search')(
        context, dict(data_dict, fq='type:deposited-dataset'))
    organizations = toolkit.get_action('organization_list')(
        context,
        { 'type': 'data-container' },
    )

    rec = TimeSeriesMetric(
        datasets_count=packages['count'],
        deposits_count=deposits['count'],
        containers_count=len(organizations),
    )
    model.Session.add(rec)
    model.Session.commit()
    model.Session.refresh(rec)
    print('Snapshot saved at {}'.format(rec.timestamp))


@unhcr.command(
    u'send-summary-emails',
    short_help=u'Send a summary of activity over the last 7 days\nto sysadmins and curators'
)
def send_summary_emails():
    if not toolkit.asbool(toolkit.config.get('ckanext.unhcr.send_summary_emails', False)):
        print('ckanext.unhcr.send_summary_emails is False. Not sending anything.')
        return

    recipients = get_summary_email_recipients()
    subject = '[UNHCR RIDL] Weekly Summary'

    for recipient in recipients:
        if recipient['email']:
            email = compose_summary_email_body(recipient)

            if email['total_events'] == 0:
                print('SKIPPING summary email to: {}'.format(recipient['email']))
                continue

            print('SENDING summary email to: {}'.format(recipient['email']))
            if self.verbose > 1:
                print(email['body'])
                print('')

            mail_user_by_id(recipient['id'], subject, email['body'])

    print('Sent weekly summary emails.')
