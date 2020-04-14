from datetime import datetime, timedelta
import logging
from ckan import model
from ckan.common import config
from ckan.plugins import toolkit
from ckan.lib import mailer as core_mailer
from ckan.lib.base import render_jinja2
from ckanext.unhcr import helpers
log = logging.getLogger(__name__)


# General

def mail_user(user, subj, body, headers={}):
    try:
        headers.setdefault('Content-Type', 'text/html; charset=UTF-8')
        core_mailer.mail_user(user, subj, body, headers=headers)
    except Exception as exception:
        log.exception(exception)


def mail_user_by_id(user_id, subj, body, headers={}):
    user = model.User.get(user_id)
    return mail_user(user, subj, body, headers=headers)


# Data Container

def compose_container_email_subj(container, event):
    return '[UNHCR RIDL] Data Container %s: %s' % (event.capitalize(), container['title'])


def compose_container_email_body(container, user, event):
    context = {}
    context['recipient'] = user.fullname or user.name
    context['site_title'] = config.get('ckan.site_title')
    context['site_url'] = config.get('ckan.site_url')
    context['container'] = container
    context['container_url'] = toolkit.url_for('data-container_read', id=container['name'], qualified=True)
    return render_jinja2('emails/container/%s.html' % event, context)


# Data Deposit

def compose_curation_email_subj(dataset):
    return '[UNHCR RIDL] Curation: %s' % dataset.get('title')


def compose_curation_email_body(dataset, curation, recipient, event, message=None):
    context = {}
    context['recipient'] = recipient
    context['site_title'] = config.get('ckan.site_title')
    context['site_url'] = config.get('ckan.site_url')
    context['dataset'] = dataset
    context['dataset_url'] = toolkit.url_for('dataset_read', id=dataset['name'], qualified=True)
    context['curation'] = curation
    context['message'] = message
    return render_jinja2('emails/curation/%s.html' % event, context)


# Membership

def compose_membership_email_subj(container):
    return '[UNHCR RIDL] Membership: %s' % container.get('title')


def compose_membership_email_body(container, user_dict, event):
    context = {}
    context['recipient'] = user_dict.get('fullname') or user_dict.get('name')
    context['site_title'] = config.get('ckan.site_title')
    context['site_url'] = config.get('ckan.site_url')
    context['container'] = container
    # single
    if isinstance(container, dict):
        context['container_url'] = toolkit.url_for('data-container_read', id=container['name'], qualified=True)
    # multiple
    else:
        for item in container:
            item['url'] = toolkit.url_for('data-container_read', id=item['name'], qualified=True)
        context['container_url'] = toolkit.url_for('data-container_index', qualified=True)
    return render_jinja2('emails/membership/%s.html' % event, context)


# Weekly Summary

def _get_new_packages(context, start_time):
    data_dict = {
        'q': '*:*',
        'fq': (
            '-type:deposited-dataset AND ' +\
            'metadata_created:[{} TO NOW]'.format(start_time)
        ),
        'sort': 'metadata_created desc',
        'include_private': True,
    }
    packages = toolkit.get_action('package_search')(context, data_dict)
    return packages['results']


def _get_new_deposits(context, start_time):
    data_dict = {
        'q': '*:*',
        'fq': (
            'type:deposited-dataset AND ' +\
            '-curation_state:review AND ' +\
            'metadata_created:[{} TO NOW]'.format(start_time)
        ),
        'sort': 'metadata_created desc',
        'include_private': True,
    }
    packages = toolkit.get_action('package_search')(context, data_dict)
    return packages['results']


def _get_deposits_awaiting_review(context, start_time):
    data_dict = {
        'q': '*:*',
        'fq': (
            'type:deposited-dataset AND ' +\
            'curation_state:review AND ' +\
            'metadata_created:[{} TO NOW]'.format(start_time)
        ),
        'sort': 'metadata_created desc',
        'include_private': True,
    }
    packages = toolkit.get_action('package_search')(context, data_dict)
    return packages['results']


def compose_summary_email_body(user_dict):
    context = {}

    start_time = datetime.now() - timedelta(days=7)
    context['start_date'] = start_time.strftime('%A %B %e %Y')
    query_start_time = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')

    context['recipient'] = user_dict.get('fullname') or user_dict.get('name')
    context['site_title'] = config.get('ckan.site_title')
    context['site_url'] = config.get('ckan.site_url')

    context['datasets_url'] = toolkit.url_for(
        'search',
        q=(
            '-type:deposited-dataset AND ' +\
            'metadata_created:[{} TO NOW]'.format(query_start_time)
        ),
        sort='metadata_created desc',
        qualified=True
    )
    context['deposits_url'] = toolkit.url_for(
        'search',
        q=(
            'type:deposited-dataset AND ' +\
            'metadata_created:[{} TO NOW]'.format(query_start_time)
        ),
        sort='metadata_created desc',
        qualified=True
    )

    action_context = { 'user': user_dict['name'] }
    context['new_datasets'] = _get_new_packages(action_context, query_start_time)
    context['new_deposits'] = _get_new_deposits(action_context, query_start_time)
    context['awaiting_review'] = _get_deposits_awaiting_review(
        action_context,
        query_start_time
    )

    context['h'] = toolkit.h

    return render_jinja2('emails/curation/summary.html', context)


def get_summary_email_recipients():
    # summary emails are sent to sysadmins
    # and members of the curation team
    recipients = []

    deposit_group = helpers.get_data_deposit()
    curators = toolkit.get_action('member_list')(
        { 'ignore_auth': True },
        { 'id': deposit_group['id'] }
    )
    curator_ids = [c[0] for c in curators]

    all_users = toolkit.get_action('user_list')({ 'ignore_auth': True }, {})
    default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })

    for user in all_users:
        if user['name'] == default_user['name']:
            continue
        if user['sysadmin'] or user['id'] in curator_ids:
            recipients.append(user)

    return recipients
