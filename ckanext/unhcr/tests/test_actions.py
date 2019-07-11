import json
import responses
from ckan import model
from pprint import pprint
from ckan.common import config
from ckan.plugins import toolkit
from nose.plugins.attrib import attr
from ckan.tests import factories as core_factories
from nose.tools import assert_raises, assert_equals
from ckanext.unhcr.tests import base, factories
from ckanext.unhcr import helpers


class TestActions(base.FunctionalTestBase):

    # General

    def setup(self):
        super(TestActions, self).setup()

        # Config
        config['ckanext.unhcr.microdata_api_key'] = 'API-KEY'

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.user = core_factories.User(name='user', id='user')

        # Datasets
        self.dataset = factories.Dataset(
            name='dataset')

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
        assert_equals(len(responses.calls), 1)
        assert_equals(call.request.url, url)
        assert_equals(call.request.headers['X-Api-Key'], 'API-KEY')
        assert_equals(call.request.headers['Content-Type'], 'application/json')
        assert_equals(json.loads(call.request.body), helpers.convert_dataset_to_microdata_survey(self.dataset, 'nation', 'repoid'))
        assert_equals(survey['url'], 'https://microdata.unhcr.org/index.php/catalog/1')

    @responses.activate
    def test_package_publish_microdata_not_valid_request(self):
        context = {'model': model, 'user': self.sysadmin['name']}

        # Patch requests
        url = 'https://microdata.unhcr.org/index.php/api/datasets/create/survey/DATASET'
        responses.add_passthru('http')
        responses.add(responses.POST, url, status=400,
            json={'status': 'failed'})

        # Publish to microdata
        with assert_raises(RuntimeError):
            toolkit.get_action('package_publish_microdata')(context, {
                'id': self.dataset['id'],
                'nation': '',
            })

    def test_package_publish_microdata_not_found(self):
        context = {'model': model, 'user': self.sysadmin['name']}
        action = toolkit.get_action('package_publish_microdata')
        assert_raises(toolkit.ObjectNotFound,
            action, context, {'id': 'bad-id'})

    def test_package_publish_microdata_not_sysadmin(self):
        context = {'model': model, 'user': self.user['name']}
        action = toolkit.get_action('package_publish_microdata')
        assert_raises(toolkit.NotAuthorized,
            action, context, {'id': self.dataset['id']})

    def test_package_publish_microdata_not_set_api_key(self):
        context = {'model': model, 'user': self.sysadmin['name']}
        action = toolkit.get_action('package_publish_microdata')
        del config['ckanext.unhcr.microdata_api_key']
        assert_raises(toolkit.NotAuthorized,
            action, context, {'id': self.dataset['id']})
