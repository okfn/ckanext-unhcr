# -*- coding: utf-8 -*-

import os

import pytest

from ckan.config import environment

from ckanext.unhcr.models import create_tables as unhcr_create_tables
from ckanext.collaborators.model import (
    tables_exist as collaborators_tables_exist,
    create_tables as collaborators_create_tables,
)


@pytest.fixture
def unhcr_migrate():
    unhcr_create_tables()
    if not collaborators_tables_exist():
        collaborators_create_tables()


@pytest.fixture(autouse=True, scope='session')
def use_test_env():
    # setup
    os.environ['CKAN_TESTING'] = 'True'
    environment.update_config()

    yield

    # teardown
    os.environ.pop('CKAN_TESTING', None)
