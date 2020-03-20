# -*- coding: utf-8 -*-

import sys

from ckan.plugins.toolkit import CkanCommand

from ckanext.unhcr.models import tables_exist, create_tables


class Unhcr(CkanCommand):
    u'''Utilities for the CKAN UNHCR extension

    Usage:
        paster unhcr init-db
            Initialize database tables

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
        else:
            self.parser.print_usage()
            sys.exit(1)

    def init_db(self):
        if tables_exist():
            print(u'UNHCR tables already exist')
            sys.exit(0)

        create_tables()
        print(u'UNHCR tables created')
