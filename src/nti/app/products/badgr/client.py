#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: model.py 123306 2017-10-19 03:47:14Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import pytz
import requests
import nameparser

from base64 import b64encode

from datetime import datetime

from zope import component
from zope import interface

from zope.component.hooks import getSite

from zope.intid.interfaces import IIntIds

from nti.app.products.badgr import NT_EVIDENCE_NTIID_ID
from nti.app.products.badgr import BADGR_INTEGRATION_NAME

from nti.app.products.badgr.interfaces import IBadgrBadge
from nti.app.products.badgr.interfaces import IBadgrClient
from nti.app.products.badgr.interfaces import BadgrClientError
from nti.app.products.badgr.interfaces import IBadgrIntegration
from nti.app.products.badgr.interfaces import IAwardedBadgrBadge
from nti.app.products.badgr.interfaces import IBadgrOrganization
from nti.app.products.badgr.interfaces import IBadgrBadgeCollection
from nti.app.products.badgr.interfaces import IBadgrInitializationUtility
from nti.app.products.badgr.interfaces import InvalidBadgrIntegrationError
from nti.app.products.badgr.interfaces import IAwardedBadgrBadgeCollection
from nti.app.products.badgr.interfaces import IBadgrOrganizationCollection
from nti.app.products.badgr.interfaces import MissingBadgrOrganizationError
from nti.app.products.badgr.interfaces import DuplicateBadgrBadgeAwardedError

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.site.localutility import install_utility

logger = __import__('logging').getLogger(__name__)


@component.adapter(IBadgrIntegration)
@interface.implementer(IBadgrClient)
def integration_to_client(integration):
    if integration.authorization_token:
        return BadgrClient(integration)


@interface.implementer(IBadgrInitializationUtility)
class _BadgrInitializationUtility(object):

    BASE_URLS = ('https://api.credly.com/v1',
                 'https://sandbox-api.credly.com/v1')

    @property
    def site(self):
        return getSite()

    @property
    def site_manager(self):
        return self.site.getSiteManager()

    def _register_integration(self, obj):
        # XXX: Clean up old at this point
        try:
            del self.site_manager[BADGR_INTEGRATION_NAME]
        except KeyError:
            pass
        obj.__name__ = BADGR_INTEGRATION_NAME
        install_utility(obj,
                        utility_name=obj.__name__,
                        provided=IBadgrIntegration,
                        local_site_manager=self.site_manager)
        return obj

    def _get_organizations(self, integration):
        client = IBadgrClient(integration)
        return client.get_organizations()

    def set_organization(self, integration):
        """
        Fetch organizations, which should be a single entry.

        Raises :class:`InvalidBadgrIntegrationError` if token is invalid.
        """
        organizations = self._get_organizations(integration)
        organizations = organizations.organizations
        if len(organizations) == 1:
            # Just one organization - set and use
            integration.organization = organizations[0]
            integration.organization.__parent__ = integration
            self._register_integration(integration)
        else:
            logger.warn("Multiple organizations tied to auth token (%s) (%s)",
                        integration.authorization_token,
                        organizations)
        return integration

    def initialize(self, integration):
        """
        We have two possible API urls; try both. If successful, integration
        will have url and organization stored on it for future API calls.
        """
        invalid_exception = None
        for base_url in self.BASE_URLS:
            integration.base_url = base_url
            try:
                self.set_organization(integration)
            except InvalidBadgrIntegrationError as exc:
                invalid_exception = exc
            else:
                return integration
        raise invalid_exception


@interface.implementer(IBadgrClient)
class BadgrClient(object):
    """
    The client to interact with badgr.
    """

    ORGANIZATIONS_URL = '/organizations'
    ORGANIZATIONS_ORG_URL = '/organizations/%s'
    ORGANIZATION_ALL_BADGES_URL = '/organizations/%s/badge_templates'
    ORGANIZATION_BADGE_URL = '/organizations/%s/badge_templates/%s'

    BADGE_URL = '/organizations/%s/badges'

    def __init__(self, integration):
        self.authorization_token = integration.authorization_token
        # The authorization token is effectively the username; encode
        # with an empty password
        self.b64_token = b64encode('%s:' % self.authorization_token)
        org_id = None
        if integration.organization:
            org_id = integration.organization.organization_id
        self.organization_id = org_id
        self.base_url = integration.base_url

    def _make_call(self, url, post_data=None, params=None, delete=False, acceptable_return_codes=None):
        if not acceptable_return_codes:
            acceptable_return_codes = (200,201)
        url = '%s%s' % (self.base_url, url)
        logger.debug('badgr badges call (url=%s) (params=%s) (post_data=%s)',
                     url, params, post_data)

        access_header = 'Basic %s' % self.b64_token
        if post_data:
            response = requests.post(url,
                                     json=post_data,
                                     headers={'Authorization': access_header,
                                              'Accept': 'application/json'})
        elif delete:
            response = requests.delete(url,
                                       headers={'Authorization': access_header})
        else:
            response = requests.get(url,
                                    params=params,
                                    headers={'Authorization': access_header})
        if response.status_code not in acceptable_return_codes:
            if response.status_code == 422:
                try:
                    error_dict = response.json()
                    if "already has this badge" in error_dict['data']['message']:
                        raise DuplicateBadgrBadgeAwardedError()
                except KeyError:
                    pass
            logger.warn('Error while making badgr API call (%s) (%s) (%s)',
                        url,
                        response.status_code,
                        response.text)
            if response.status_code == 401:
                raise InvalidBadgrIntegrationError(response.text)
            raise BadgrClientError(response.text)
        return response

    def get_badge(self, badge_template_id):
        """
        Get the :class:`IBadgrBadge` associated with the template id.
        """
        if not self.organization_id:
            raise MissingBadgrOrganizationError()
        url = self.ORGANIZATION_BADGE_URL % (self.organization_id, badge_template_id)
        result = self._make_call(url)
        result = IBadgrBadge(result.json())
        return result

    def get_badges(self, sort=None, filters=None, page=None):
        """
        Return an :class:`IBadgrBadgeCollection`.

        https://www.yourbadgr.com/docs/badge_templates
        """
        if not self.organization_id:
            raise MissingBadgrOrganizationError()
        params = dict()
        filters = dict(filters) if filters else dict()
        filters['state'] = 'active'
        if sort:
            params['sort'] = self._get_sort_str(sort)
        if filters:
            params['filter'] = self._get_filter_str(filters)
        if page:
            params['page'] = page
        url = self.ORGANIZATION_ALL_BADGES_URL % self.organization_id
        result = self._make_call(url, params=params)
        result = IBadgrBadgeCollection(result.json())
        return result

    def get_organization(self, organization_id):
        """
        Get the :class:`IBadgrOrganization` for this organization id.
        """
        url = self.ORGANIZATIONS_ORG_URL % organization_id
        result = self._make_call(url)
        result = IBadgrOrganization(result.json())
        return result

    def get_organizations(self):
        """
        Get all :class:`IBadgrOrganization` objects.
        """
        url = self.ORGANIZATIONS_URL
        result = self._make_call(url)
        result = IBadgrOrganizationCollection(result.json())
        return result

    def _get_user_id(self, user):
        intids = component.getUtility(IIntIds)
        return intids.getId(user)

    def _get_user_email(self, user):
        result = IUserProfile(user).email
        return result

    def _get_filter_str(self, filter_dict):
        result = []
        for key, val in filter_dict.items():
            result.append('%s::%s' % (key, val))
        return '|'.join(result)

    def _get_sort_str(self, sort_seq):
        return '|'.join(sort_seq)

    def _get_formatted_date(self, date_obj=None):
        if not date_obj:
            date_obj = datetime.utcnow()
        if not date_obj.tzinfo:
            date_obj = date_obj.replace(tzinfo=pytz.UTC)
        return date_obj.strftime("%Y-%m-%d %H:%M:%S %z")

    def get_awarded_badges(self, user, sort=None, filters=None, page=None,
                           public_only=None, accepted_only=False):
        """
        Return an :class:`IAwardedBadgrBadgeCollection`.

        https://www.yourbadgr.com/docs/issued_badges filtered by user email.
        """
        if not self.organization_id:
            raise MissingBadgrOrganizationError()
        params = dict()
        filters = dict(filters) if filters else dict()
        # We want *all* badges tied to this user (by email) in Badgr. The
        # user may have multiple email addresses on their Badgr account.
        filters['recipient_email_all'] = self._get_user_email(user)
        if public_only:
            filters['public'] = 'true'
        # We only want pending or accepted badges (not revoked or rejected)
        if accepted_only:
            filters['state'] = 'accepted'
        else:
            filters['state'] = 'pending,accepted'
        if sort:
            params['sort'] = self._get_sort_str(sort)
        if filters:
            params['filter'] = self._get_filter_str(filters)
        if page is not None:
            params['page'] = page
        url = self.BADGE_URL % self.organization_id
        result = self._make_call(url, params=params)
        result = IAwardedBadgrBadgeCollection(result.json())
        # FIXME: fix this
        for awarded_badge in result.Items:
            awarded_badge.User = user
        return result

    def award_badge(self, user, badge_template_id, suppress_badge_notification_email=False,
                    locale=None, evidence_ntiid=None, evidence_title=None, evidence_desc=None):
        """
        Award a badge to a user.

        https://www.yourbadgr.com/docs/issued_badges
        """
        if not self.organization_id:
            raise MissingBadgrOrganizationError()
        data = dict()
        # We award this to our user's email address - no
        # matter if invalid, bounced etc.
        data['recipient_email'] = self._get_user_email(user)

        # TODO: Raise if no real name? Is this possible?
        friendly_named = IFriendlyNamed(user)
        if friendly_named.realname and '@' not in friendly_named.realname:
            human_name = nameparser.HumanName(friendly_named.realname)
            data['issued_to_first_name'] = human_name.first
            data['issued_to_last_name'] = human_name.last
        data['badge_template_id'] = badge_template_id
        data['issuer_earner_id'] = self._get_user_id(user)
        data['issued_at'] = self._get_formatted_date()
        data['suppress_badge_notification_email'] = suppress_badge_notification_email
        if locale:
            data['locale'] = locale
        if evidence_ntiid:
            assert is_valid_ntiid_string(evidence_ntiid)
            evidence_id = '%s=%s' % (NT_EVIDENCE_NTIID_ID, evidence_ntiid)
            data['evidence'] = [{"type": "IdEvidence",
                                 "title": evidence_title,
                                 "description": evidence_desc,
                                 "id": evidence_id}]
        url = self.BADGE_URL % self.organization_id
        result = self._make_call(url, post_data=data)
        result = IAwardedBadgrBadge(result.json())
        return result

