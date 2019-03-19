.PHONY: assets debug docker e2e i18n readme start shell test


list:
	@grep '^\.PHONY' Makefile | cut -d' ' -f2- | tr ' ' '\n'


assets:
	npx grunt concat
	npx grunt postcss

docker:
	docker pull openknowledge/ckan-base:2.7 && \
	docker pull openknowledge/ckan-dev:2.7 && \
	docker-compose -f ../../docker-compose.dev.yml build

e2e:
	npx nightwatch

i18n:
	# docker-compose -f ../../docker-compose.dev.yml exec ckan-dev 'cd /srv/app/src_extensions/ckanext-unhcr && python setup.py extract_messages'
	docker-compose -f ../../docker-compose.dev.yml exec ckan-dev 'cd /srv/app/src_extensions/ckanext-unhcr && python setup.py compile_catalog -l en -f'

readme:
	npx doctoc README.md

start:
	docker-compose -f ../../docker-compose.dev.yml up

shell:
	docker-compose -f ../../docker-compose.dev.yml exec ckan-dev bash

test:
	docker-compose -f ../../docker-compose.dev.yml exec ckan-dev nosetests --ckan --nologcapture -s -v --with-pylons=/srv/app/src_extensions/ckanext-unhcr/test.ini --with-coverage --cover-package=ckanext.unhcr --cover-inclusive --cover-erase --cover-tests /srv/app/src_extensions/ckanext-unhcr/ckanext/unhcr/tests/test_controllers.py:TestDepositedDatasetController ${ARGS}
