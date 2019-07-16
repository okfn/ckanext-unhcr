import logging
from ckan import model
from ckan.common import config
from ckan.plugins import toolkit
from ckan.lib import mailer as core_mailer
from ckan.lib.base import render_jinja2
import ckan.logic.action.get as get_core
from ckanext.unhcr import helpers
log = logging.getLogger(__name__)


# General

def mail_user(user, subj, body, headers={}):
    try:
        core_mailer.mail_user(user, subj, body, headers=headers)
    except Exception as exception:
        log.exception(exception)


def mail_user_by_id(user_id, subj, body):
    user = model.User.get(user_id)
    headers = {'Content-Type': 'text/html; charset=UTF-8'}
    return mail_user(user, subj, body, headers=headers)


# Misc

def mail_data_container_request_to_sysadmins(context, org_dict):
    context.setdefault('model', model)

    # Mail all sysadmins
    for user in helpers.get_sysadmins():
        if user.email:
            subj = compose_container_email_subj(org_dict, event='request')
            body = compose_container_email_body(org_dict, user, event='request')
            mail_user(user, subj, body)


def mail_data_container_update_to_user(context, org_dict, event='approval'):
    context.setdefault('model', model)

    # Mail all members
    for member in get_core.member_list(context, {'id': org_dict['id']}):
        user = model.User.get(member[0])
        if user and user.email:
            subj = compose_container_email_subj(org_dict, event=event)
            body = compose_container_email_body(org_dict, user, event=event)
            mail_user(user, subj, body)


# Data Container

def compose_container_email_subj(org_dict, event='request'):
    return '[UNHCR RIDL] Data Container {0}: {1}'.format(event.capitalize(), org_dict['title'])


def compose_container_email_body(org_dict, user, event='request'):
    org_link = toolkit.url_for('data-container_read', id=org_dict['name'], qualified=True)
    return render_jinja2('emails/data_container_{0}.txt'.format(event), {
        'user_name': user.fullname or user.name,
        'site_title': config.get('ckan.site_title'),
        'site_url': config.get('ckan.site_url'),
        'org_title': org_dict['title'],
        'org_link': org_link,
    })


# Data Deposit

def compose_curation_email_subj(dataset):
    return '[UNHCR RIDL] Curation: %s' % dataset.get('title')


def compose_curation_email_body(dataset, curation, recipient, event, message=None):
    context = {}
    context['site_title'] = config.get('ckan.site_title')
    context['site_url'] = config.get('ckan.site_url')
    context['dataset'] = dataset
    context['dataset_url'] = toolkit.url_for('dataset_read', id=dataset['name'], qualified=True)
    context['curation'] = curation
    context['recipient'] = recipient
    context['message'] = message
    return render_jinja2('emails/curation_%s.html' % event, context)
