# -*- coding: utf-8 -*-

import sys

from ckan.plugins import toolkit

import ckan.model as model
from ckanext.unhcr.models import tables_exist, create_tables, TimeSeriesMetric
from ckanext.unhcr.mailer import (
    compose_summary_email_body,
    get_summary_email_recipients,
    mail_user_by_id
)


class Unhcr(toolkit.CkanCommand):
    u'''Utilities for the CKAN UNHCR extension

    Usage:
        paster unhcr init-db
            Initialize database tables

        paster unhcr snapshot-metrics
            Take a snapshot of time-series metrics

        paster unhcr send-summary-emails
            Send a summary of activity over the last 7 days
            to sysadmins and curators
    '''
    summary = __doc__.split('\n')[0]
    usage = __doc__
    max_args = 9
    min_args = 0

    def __init__(self, name):
        super(Unhcr, self).__init__(name)

    def command(self):
        self._load_config()

        if len(self.args) != 1:
            self.parser.print_usage()
            sys.exit(1)

        cmd = self.args[0]
        if cmd == 'init-db':
            self.init_db()
        elif cmd == 'snapshot-metrics':
            self.snapshot_metrics()
        elif cmd == 'send-summary-emails':
            self.send_summary_emails()
        else:
            self.parser.print_usage()
            sys.exit(1)

    def init_db(self):
        if tables_exist():
            print(u'UNHCR tables already exist')
            sys.exit(0)

        create_tables()
        print(u'UNHCR tables created')

    def snapshot_metrics(self):
        context = { 'ignore_auth': True }

        packages = toolkit.get_action('package_search')(context, {
            'q': '*:*',
            'fq': "-type:deposited-dataset",
            'rows': 0,
            'include_private': True,
        })
        organizations = toolkit.get_action('organization_list')(
            context,
            { 'type': 'data-container' },
        )

        rec = TimeSeriesMetric(
            datasets_count=packages['count'],
            containers_count=len(organizations),
        )
        model.Session.add(rec)
        model.Session.commit()
        model.Session.refresh(rec)
        print('Snapshot saved at {}'.format(rec.timestamp))

    def send_summary_emails(self):
        recipients = get_summary_email_recipients()
        subject = '[UNHCR RIDL] Weekly Summary'

        for recipient in recipients:
            if recipient['email']:
                print('Sending summary email to: {}'.format(recipient['email']))

                body = compose_summary_email_body(recipient)
                if self.verbose > 1:
                    print(body)
                    print('')

                mail_user_by_id(recipient['id'], subject, body)

        print('Sent weekly summary emails.')
