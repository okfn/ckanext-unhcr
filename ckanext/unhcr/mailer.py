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
    context['site_title'] = config.get('ckan.site_title')
    context['site_url'] = config.get('ckan.site_url')
    context['container'] = container
    context['container_url'] = toolkit.url_for('data-container_read', id=container['name'], qualified=True)
    context['recipient'] = user.fullname or user.name
    return render_jinja2('emails/container/%s.html' % event, context)


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
    return render_jinja2('emails/curation/%s.html' % event, context)


# Membership

def compose_membership_email_subj(container):
    return '[UNHCR RIDL] Membership: %s' % container.get('title')


def compose_membership_email_body(container, user_dict, event):
    context = {}
    context['site_title'] = config.get('ckan.site_title')
    context['site_url'] = config.get('ckan.site_url')
    context['container'] = container
    context['container_url'] = toolkit.url_for('data-container_read', id=container['name'], qualified=True)
    context['recipient'] = user_dict.get('fullname') or user_dict.get('name')
    return render_jinja2('emails/membership/%s.html' % event, context)
