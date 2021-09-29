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

from zope.cachedescriptors.property import Lazy

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
from nti.app.products.badgr.interfaces import IBadgrAuthorizedIntegration
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


@component.adapter(IBadgrAuthorizedIntegration)
@interface.implementer(IBadgrClient)
def integration_to_client(integration):
    return BadgrClient(integration)


@interface.implementer(IBadgrInitializationUtility)
class _BadgrInitializationUtility(object):

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
                        provided=IBadgrAuthorizedIntegration,
                        local_site_manager=self.site_manager)
        return obj

    def _get_issuers(self, integration):
        client = IBadgrClient(integration)
        return client.get_issuers()

    def set_issuer(self, integration):
        """
        Fetch issuers, which should be a single entry.

        Raises :class:`InvalidBadgrIntegrationError` if token is invalid.
        """
        issuers = self._get_issuers(integration)
        issuers = issuers.issuers
        if len(issuers) == 1:
            # Just one issuer - set and use
            integration.issuer = issuers[0]
            integration.issuer.__parent__ = integration
            self._register_integration(integration)
        else:
            logger.warn("Multiple issuers tied to auth token (%s) (%s)",
                        integration.access_token,
                        issuers)
        return integration

    def initialize(self, integration):
        self.set_issuer(integration)
        return integration


@interface.implementer(IBadgrClient)
class BadgrClient(object):
    """
    The client to interact with badgr.
    """

    BASE_URL = 'https://api.badgr.io/v2'

    ISSUERS_URL = '/issuers'
    ISSUERS_ORG_URL = '/issuers/%s'
    ISSUER_ALL_BADGES_URL = '/issuers/%s/badgeclasses'
    ORGANIZATION_BADGE_URL = '/badgeclasses/%s'
    ISSUER_ASSERTIONS = '/issuers/%s/assertions'

    BADGE_URL = '/organizations/%s/badges'

    def __init__(self, authorized_integration):
        self.authorized_integration = authorized_integration

    @Lazy
    def _access_token(self):
        return self.authorized_integration.access_token

    def _update_access_token(self):
        result = self.authorized_integration.update_tokens(self._access_token)
        self._access_token = result

    def _make_call(self, url, post_data=None, params=None, delete=False, acceptable_return_codes=None):
        if not acceptable_return_codes:
            acceptable_return_codes = (200, 201)
        url = '%s%s' % (self.BASE_URL, url)
        logger.debug('badgr badges call (url=%s) (params=%s) (post_data=%s)',
                     url, params, post_data)

        def _do_make_call():
            access_header = 'Bearer %s' % self._access_token
            if post_data:
                return requests.post(url,
                                     json=post_data,
                                     headers={'Authorization': access_header,
                                              'Accept': 'application/json'})
            elif delete:
                return requests.delete(url,
                                       headers={'Authorization': access_header})
            else:
                return requests.get(url,
                                    headers={'Authorization': access_header})
        response = _do_make_call()
        if response.status_code in (401, 403):
            # Ok, expired token, refresh and try again.
            self._update_access_token()
            response = _do_make_call()
        
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

