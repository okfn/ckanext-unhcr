import logging
from ckan import model
from ckan.plugins import toolkit
from ckan.plugins.toolkit import Invalid, missing, get_validator, _
from ckan.logic import validators
from ckanext.scheming.validation import scheming_validator
from ckanext.scheming import helpers as sh
from ckanext.unhcr import helpers, utils
log = logging.getLogger(__name__)

OneOf = get_validator('OneOf')


# Attachments

def ignore_if_attachment(key, data, errors, context):
    index = key[1]
    if _is_attachment(index, data):
        data.pop(key, None)
        raise toolkit.StopOnError


def _is_attachment(index, data):
    for field, value in data.iteritems():
        if (field[0] == 'resources' and
                field[1] == index and
                field[2] == 'type' and
                value == 'attachment'):
            return True
    return False


# Linked datasets

def linked_datasets(value, context):
    if context.get('job'):
        return value

    # Check if the user has access to the linked datasets
    selected = utils.normalize_list(value)
    allowed = _get_allowed_linked_datasets()
    for id in selected:
        if id not in allowed:
            raise Invalid('Invalid linked datasets')

    return value


# TODO:
# it could be better to extract core linked datasets
# preparing function to use here and in the helpers
def _get_allowed_linked_datasets():
    datasets = []
    for container in helpers.get_linked_datasets_for_form():
        for dataset in container['children']:
            datasets.append(dataset['value'])
    return datasets


# Unser choices

@scheming_validator
def unhcr_choices(field, schema):
    """
    Require that one of the field choices values is passed.
    """
    def validator(value):
        if value is missing or not value:
            return value
        choices = sh.scheming_field_choices(field)
        for c in choices:
            if value == c['value']:
                return value
        msg = '''
Unexpected choice "{value}". It must be either the label or the code in
brackets of one of the following: {allowed}. If you want to add another
value please contact the Site Administrators.
'''
        raise Invalid(_(
            msg.format(
                value=value,
                allowed=', '.join(
                    [c['label'] + ' [' + c['value'] + ']' for c in choices]))
            )
        )

    return validator


# Deposited Datasets

def deposited_dataset_owner_org(value, context):

    # Pass validation if data container exists and for depositing
    deposit = helpers.get_data_deposit()
    if value == deposit['id']:
        return value

    raise Invalid('Invalid data deposit')



def deposited_dataset_owner_org_dest(value, context):
    user = context.get('user')
    userobj = model.User.get(user)

    include_ids = []
    package = context.get('package')
    dataset = None
    if package:
        # 'Package' object has no attribute 'owner_org_dest'
        dataset = toolkit.get_action('package_show')(context, {'id': package.id})
        include_ids = [dataset['owner_org_dest']]

    # Pass validation if data container exists and NOT for depositing
    deposit = helpers.get_data_deposit()
    orgs = helpers.get_all_data_containers(
        exclude_ids=[deposit['id']],
        include_unknown=True,
        userobj=userobj,
        include_ids=include_ids,
        dataset=dataset,
    )
    for org in orgs:
        if value == org['id']:
            return value

    raise Invalid('Invalid data container')


def deposited_dataset_curation_state(value, context):
    ALLOWED = ['draft', 'submitted', 'review']

    # Set default value
    if not value:
        value = 'draft'

    # Raise if not allowed
    if value not in ALLOWED:
        raise Invalid('Invalid curation state')

    return value


def deposited_dataset_curator_id(value, context):

    dataset = None
    allowed_roles = ['admin', 'curator']
    if context.get('package'):
        dataset = toolkit.get_action('package_show')(
            context,
            {'id': context['package'].id}
        )
        allowed_roles.append('container admin')

    # Get curation role and raise if not curator
    if value:
        curation_role = helpers.get_deposited_dataset_user_curation_role(value, dataset)
        if curation_role not in allowed_roles:
            raise Invalid('Invalid Curator id')

    return value


# Private datasets

def always_false_if_not_sysadmin(value, context):
    user_name = context.get('user')
    user = model.User.get(user_name)
    if value is not None and value is not toolkit.missing and user and user.sysadmin:
        return value
    else:
        return False


def visibility_validator(key, data, error, context):
    ''' Validates visibility has a correct value.

    Visibility only has two values in the schema, 'restricted' and 'public'. The
    value 'private' is used only to setup the actual private field if needed.
    '''
    value = data.get(key)

    if value not in ('private', 'restricted', 'public'):
        raise Invalid('Invalid value for the visibility field')

    # Set the actual private field
    if value == 'private':
        data[('private',)] = True
        data[('visibility',)] = 'restricted'
    else:
        data[('private',)] = False


# File types

def file_type_validator(key, data, errors, context):
    index = key[1]
    value = data.get(key)
    attach = _is_attachment(index, data)
    if (attach and value == 'microdata') or (not attach and value != 'microdata'):
        raise Invalid('Invalid value for the "file_type" field')


# Uploads

def upload_not_empty(key, data, errors, context):
    index = key[1]
    id_key = ('resources', index, 'id')
    type_key = ('resources', index, 'type')

    # The two options here are "attachment" and "data"
    # "data" must be a file upload, "attachment" can be a URL
    is_data = data.get(type_key) == 'data'

    # We only want to enforce this rule for "data" resources on create
    # if we're editing an existing resource, we will already have an uploaded file
    is_create = not data.get(id_key) or data.get(id_key) is missing
    is_update = not is_create

    upload_missing = (
        (is_data and is_create and not data[('resources', index, 'url_type')] == 'upload') or
        (is_data and is_update and not data.get(('resources', index, 'url',)))
    )

    if upload_missing:
        errors[('resources', index, 'url',)] = ['All data resources require an uploaded file']


# Custom Activities

_object_id_validators = {
    'download resource': validators.package_id_exists,
}

def object_id_validator(key, activity_dict, errors, context):
    '''Validate the 'object_id' value of an activity_dict.

    This wraps ckan.logic.validators.object_id_validator to support additional
    object types
    '''
    activity_type = activity_dict[('activity_type',)]
    if activity_type in _object_id_validators:
        object_id = activity_dict[('object_id',)]
        return _object_id_validators[activity_type](object_id, context)
    return validators.object_id_validator(key, activity_dict, errors, context)


def activity_type_exists(activity_type):
    '''Wrap ckan.logic.validators.activity_type_exists to support additional
    activity stream types
    '''
    if activity_type in _object_id_validators:
        return activity_type
    return validators.activity_type_exists(activity_type)


# Collaborators

def owner_org_validator(key, data, errors, context):
    user = context.get('user')
    package = context.get('package')

    userobj = model.User.get(user)
    if userobj and userobj.sysadmin:
        return validators.owner_org_validator(key, data, errors, context)

    action = toolkit.get_action('package_collaborator_list_for_user')
    if user and action and package:
        try:
            datasets = action(context, {'id': user})
        except toolkit.ObjectNotFound:
            datasets = []
        if package.id in [d['package_id'] for d in datasets]:
            if data.get(key) == package.owner_org:
                try:
                    return validators.owner_org_validator(key, data, errors, context)
                except Invalid as e:
                    if e.error in (
                        u'You cannot add a dataset to this organization',
                        u'You cannot add a dataset to this data container',
                    ):
                        return
                    raise e
            raise Invalid('You cannot move this dataset to another data container')

    return validators.owner_org_validator(key, data, errors, context)
