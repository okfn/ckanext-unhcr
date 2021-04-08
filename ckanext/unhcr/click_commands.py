# -*- coding: utf-8 -*-

import click
from ckanext.unhcr.models import create_tables


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
