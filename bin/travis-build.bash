#!/bin/bash
set -e

echo "This is travis-build.bash..."

echo "Installing the packages that CKAN requires..."
sudo apt-get update -qq
sudo apt-get install solr-jetty

echo "Installing CKAN and its Python dependencies..."
git clone https://github.com/ckan/ckan
cd ckan
if [ $CKANVERSION == 'master' ]
then
    echo "CKAN version: master"
else
    CKAN_TAG=$(git tag | grep ^ckan-$CKANVERSION | sort --version-sort | tail -n 1)
    git checkout $CKAN_TAG
    echo "CKAN version: ${CKAN_TAG#ckan-}"
fi
echo "Patching CKAN core..."
for d in $TRAVIS_BUILD_DIR/bin/patches/*; do \
    for f in `ls $d/*.patch | sort -g`; do \
	    echo "$0: Applying patch $f"; patch -p1 < "$f" ; \
    done ; \
done

python setup.py develop
pip install -r requirements.txt
pip install -r dev-requirements.txt
cd -

echo "Creating the PostgreSQL user and database..."
sudo -u postgres psql -c "CREATE USER ckan_default WITH PASSWORD 'pass';"
sudo -u postgres psql -c "CREATE USER datastore_default WITH PASSWORD 'pass';"
sudo -u postgres psql -c 'CREATE DATABASE ckan_test WITH OWNER ckan_default;'
sudo -u postgres psql -c 'CREATE DATABASE datastore_test WITH OWNER ckan_default;'


echo "Setting up Solr..."
# Solr is multicore for tests on ckan master, but it's easier to run tests on
# Travis single-core. See https://github.com/ckan/ckan/issues/2972
printf "NO_START=0\nJETTY_HOST=127.0.0.1\nJETTY_PORT=8983\nJAVA_HOME=$JAVA_HOME" | sudo tee /etc/default/jetty
sudo cp ckan/ckan/config/solr/schema.xml /etc/solr/conf/schema.xml
sudo service jetty restart
sed -i -e 's/solr_url.*/solr_url = http:\/\/127.0.0.1:8983\/solr/' ckan/test-core.ini

echo "Initialising the database..."
cd ckan
paster db init -c test-core.ini
cd -

echo "Installing other extensions required..."
git clone https://github.com/ckan/ckanext-scheming
cd ckanext-scheming
python setup.py develop
pip install -r requirements.txt
cd -

git clone https://github.com/okfn/ckanext-hierarchy
cd ckanext-hierarchy
python setup.py develop
cd -

echo "Installing ckanext-unhcr and its requirements..."
python setup.py develop
pip install --upgrade -r requirements.txt
# Change the path the core test ini file as the docker compose scripts change this
# locally
sed -i -e 's/config:..\/..\/src\/ckan\/test-core.ini/config:..\/ckan\/test-core.ini/' test.ini

echo "Initialising unhcr extension tables..."
paster --plugin=ckanext-unhcr unhcr init-db -c ckan/test-core.ini

echo "Moving test.ini into a subdir..."
mkdir subdir
mv test.ini subdir

echo "travis-build.bash is done."
