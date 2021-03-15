# -*- coding: utf-8 -*-

import pytest
import json
import responses
from ckan import model
from ckan.plugins import toolkit
from ckan.tests import factories as core_factories
from ckanext.unhcr.tests import factories
from ckanext.unhcr import helpers


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestMicrodata(object):

    # General

    def setup(self):
        # Config
        toolkit.config['ckanext.unhcr.microdata_api_key'] = 'API-KEY'

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.user = core_factories.User(name='user', id='user')

        # Datasets
        self.dataset = factories.Dataset(name='dataset')

    @responses.activate
    def test_package_publish_microdata(self):
        context = {'model': model, 'user': self.sysadmin['name']}

        # Patch requests
        url = 'https://microdata.unhcr.org/index.php/api/datasets/create/survey/DATASET'
        responses.add_passthru('http')
        responses.add(responses.POST, url, status=200,
            json={'status': 'success', 'dataset': {'id': 1},})

        # Publish to microdata
        survey = toolkit.get_action('package_publish_microdata')(context, {
            'id': self.dataset['id'],
            'nation': 'nation',
            'repoid': 'repoid',
        })

        # Check calls
        call = responses.calls[0]
        assert len(responses.calls) == 1
        assert call.request.url == url
        assert call.request.headers['X-Api-Key'] == 'API-KEY'
        assert call.request.headers['Content-Type'] == 'application/json'
        assert (
            json.loads(call.request.body) ==
            helpers.convert_dataset_to_microdata_survey(self.dataset, 'nation', 'repoid')
        )
        assert survey['url'] == 'https://microdata.unhcr.org/index.php/catalog/1'

    @responses.activate
    def test_package_publish_microdata_not_valid_request(self):
        context = {'model': model, 'user': self.sysadmin['name']}

        # Patch requests
        url = 'https://microdata.unhcr.org/index.php/api/datasets/create/survey/DATASET'
        responses.add_passthru('http')
        responses.add(responses.POST, url, status=400,
            json={'status': 'failed'})

        # Publish to microdata
        with pytest.raises(RuntimeError):
            toolkit.get_action('package_publish_microdata')(context, {
                'id': self.dataset['id'],
                'nation': '',
            })

    def test_package_publish_microdata_not_found(self):
        context = {'model': model, 'user': self.sysadmin['name']}
        action = toolkit.get_action('package_publish_microdata')
        with pytest.raises(toolkit.ObjectNotFound):
            action(context, {'id': 'bad-id'})

    def test_package_publish_microdata_not_sysadmin(self):
        context = {'model': model, 'user': self.user['name']}
        action = toolkit.get_action('package_publish_microdata')
        with pytest.raises(toolkit.NotAuthorized):
            action(context, {'id': self.dataset['id']})

    def test_package_publish_microdata_not_set_api_key(self):
        context = {'model': model, 'user': self.sysadmin['name']}
        action = toolkit.get_action('package_publish_microdata')
        del toolkit.config['ckanext.unhcr.microdata_api_key']
        with pytest.raises(toolkit.NotAuthorized):
            action(context, {'id': self.dataset['id']})
