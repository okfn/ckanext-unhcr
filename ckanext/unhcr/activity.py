from ckan import model
import ckan.plugins.toolkit as toolkit


def log_download_activity(context, resource_id):
    """Log a resource download activity in the activity stream
    """
    user = context['user']
    user_id = None
    user_by_name = model.User.by_name(user.decode('utf8'))
    if user_by_name is not None:
        user_id = user_by_name.id

    resource = toolkit.get_action('resource_show')(context, {'id': resource_id})

    activity_dict = {
        'activity_type': 'download resource',
        'user_id': user_id,
        'object_id': resource['package_id'],
        'data': resource
    }

    activity_create_context = {
        'model': model,
        'user': user_id or user,
        'defer_commit': False,
        'ignore_auth': True,
    }

    create_activity = toolkit.get_action('activity_create')
    create_activity(activity_create_context, activity_dict)
