# -*- coding: utf-8 -*-

import sys

from ckan.plugins import toolkit

import ckan.model as model
from ckanext.unhcr.models import tables_exist, create_tables, TimeSeriesMetric


class Unhcr(toolkit.CkanCommand):
    u'''Utilities for the CKAN UNHCR extension

    Usage:
        paster unhcr init-db
            Initialize database tables

        paster unhcr snapshot-metrics
            Take a snapshot of time-series metrics

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
        context = { 'user': toolkit.c.user }

        packages = toolkit.get_action('package_search')(context, {
            'q': '*:*',
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
