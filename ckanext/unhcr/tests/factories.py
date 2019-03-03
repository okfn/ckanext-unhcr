from ckan.tests import factories


class DataContainer(factories.Organization):

    type = 'data-container'

    country = ['SVN']
    geographic_area = 'southern_africa'


class Dataset(factories.Dataset):

    unit_of_measurement = 'individual'
    keywords = ['shelter', 'health']
    archived = 'False'
    data_collector = ['acf']
    data_collection_technique = 'f2f'
    sampling_procedure = 'nonprobability'
    operational_purpose_of_data = 'cartography'


class DepositedDataset(factories.Dataset):

    type = 'deposited-dataset'

    owner_org = 'id-data-deposit'
    owner_org_dest = 'id-data-target'
