from ckanext.unhcr.jobs import _modify_package


# date_range

def test_modify_package_date_range():
    package = _modify_package({
        'date_range_start': None,
        'date_range_end': None,
        'resources': [
            {'date_range_start': '2017-01-01', 'date_range_end': '2017-06-01'},
            {'date_range_start': '2017-03-01', 'date_range_end': '2017-09-01'},
        ]
    })
    assert package['date_range_start'] == '2017-01-01'
    assert package['date_range_end'] == '2017-09-01'


def test_modify_package_date_range_after_resource_deletion():
    package = _modify_package({
        'date_range_start': '2017-01-01',
        'date_range_end': '2017-09-01',
        'resources': [
            {'date_range_start': '2017-01-01', 'date_range_end': '2017-06-01'},
        ]
    })
    assert package['date_range_start'] == '2017-01-01'
    assert package['date_range_end'] == '2017-06-01'


def test_modify_package_date_range_no_resources():
    package = _modify_package({
        'date_range_start': None,
        'date_range_end': None,
        'resources': [],
    })
    assert package['date_range_start'] == None
    assert package['date_range_end'] == None


# process_status

def test_modify_package_process_status():
    package = _modify_package({
        'process_status': None,
        'resources': [
            {'process_status': 'cleaned'},
            {'process_status': 'final'},
        ]
    })
    assert package['process_status'] == 'cleaned'


def test_modify_package_process_status_resource_deletion():
    package = _modify_package({
        'process_status': 'cleaned',
        'resources': [
            {'process_status': 'final'},
        ]
    })
    assert package['process_status'] == 'final'


def test_modify_package_process_status_none():
    package = _modify_package({
        'process_status': None,
        'resources': [
            {'process_status': 'cleaned'},
            {'process_status': 'final'},
        ]
    })
    assert package['process_status'] == 'cleaned'


def test_modify_package_process_status_no_resources():
    package = _modify_package({
        'process_status': 'final',
        'resources': [],
    })
    assert package['process_status'] == None


def test_modify_package_process_status_default():
    package = _modify_package({
        'process_status': None,
        'resources': [],
    })
    assert package['process_status'] == None


# privacy

def test_modify_package_privacy():
    package = _modify_package({
        'identifiability': None,
        'private': False,
        'resources': [
            {'identifiability': 'anonymized'},
        ]
    })
    assert package['identifiability'] == 'anonymized'
    assert package['private'] == False


def test_modify_package_privacy_private_false():
    package = _modify_package({
        'identifiability': None,
        'private': False,
        'resources': [
            {'identifiability': 'anonymized'},
        ]
    })
    assert package['identifiability'] == 'anonymized'
    assert package['private'] == False


def test_modify_package_privacy_resource_addition():
    package = _modify_package({
        'identifiability': 'anonymized',
        'private': False,
        'resources': [
            {'identifiability': 'anonymized'},
            {'identifiability': 'personally_identifiable'},
        ]
    })
    assert package['identifiability'] == 'personally_identifiable'
    assert package['private'] == True


def test_modify_package_privacy_package_none():
    package = _modify_package({
        'identifiability': None,
        'private': False,
        'resources': [
            {'identifiability': 'personally_identifiable'},
        ]
    })
    assert package['identifiability'] == 'personally_identifiable'
    assert package['private'] == True


def test_modify_package_privacy_default():
    package = _modify_package({
        'identifiability': None,
        'private': False,
        'resources': []
    })
    assert package['identifiability'] == None
    assert package['private'] == False
