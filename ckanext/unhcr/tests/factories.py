from ckan.tests import factories


class Dataset(factories.Dataset):

    unit_of_measurement = 'individual'
    keywords = ['shelter', 'health']
    archived = 'False'
    data_collector = ['acf']
    data_collection_technique = 'interview'
    operational_purpose_of_data = 'cartography'


class DataContainer(factories.Organization):

    type = 'data-container'

    country = ['SVN']
    geographic_area = 'southern_africa'
