#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,expression-not-assigned

from zope import interface

from zope.annotation.interfaces import IAttributeAnnotatable

from nti.app.products.integration.interfaces import IIntegration
from nti.app.products.integration.interfaces import IOAuthAuthorizedIntegration

from nti.base.interfaces import ICreated
from nti.base.interfaces import ILastModified

from nti.coremetadata.interfaces import IShouldHaveTraversablePath

from nti.schema.field import Int
from nti.schema.field import Bool
from nti.schema.field import Object
from nti.schema.field import HTTPURL
from nti.schema.field import ValidText
from nti.schema.field import ListOrTuple
from nti.schema.field import ValidDatetime
from nti.schema.field import DecodingValidTextLine as ValidTextLine


class IBadgrInitializationUtility(interface.Interface):

    def initialize(self, integration):
        """
        Handles initializing the :class:`IBadgrIntegration`, which involves finding
        the base_url and picking an issuer.
        """


class IBadgrEvidence(interface.Interface):
    """
    An Badgr badge evidence.
    """

    type = ValidTextLine(title=u'badgr evidence type',
                          min_length=1,
                          required=True)


class IBadgrIdEvidence(IBadgrEvidence):
    """
    An Badgr badge evidence.
    """

    ntiid = ValidTextLine(title=u'badgr organization id',
                          min_length=1,
                          required=True)


    name = ValidTextLine(title=u'badgr evidence name',
                         min_length=1,
                         required=False)


class IBadgrType(IShouldHaveTraversablePath, IAttributeAnnotatable):

    entity_type = ValidTextLine(title=u'badgr type',
                                min_length=1,
                                required=False)
    
    name = ValidTextLine(title=u'badgr name',
                         min_length=1,
                         required=False)
    
    open_badge_id = ValidTextLine(title=u'open badge id',
                                  min_length=1,
                                  required=False)

    entity_id = ValidTextLine(title=u'entity_id',
                              min_length=1,
                              required=True)

    image_string = ValidTextLine(title=u'image',
                                 min_length=1,
                                 required=False)

class IBadgrIssuer(IBadgrType):
    """
    An Badgr issuer.
    """

    url = ValidTextLine(title=u'Website url',
                        min_length=1,
                        required=False)

    email = ValidTextLine(title=u'Contact email',
                          min_length=1,
                          required=False)


class IBadgrIntegration(IIntegration):
    """
    Badgr integration
    """


class IBadgrAuthorizedIntegration(IOAuthAuthorizedIntegration,
                                  IBadgrIntegration):
    """
    An :class:`IOAuthAuthorizedIntegration` for badgr.
    """


class IBadgrClient(interface.Interface):
    """
    An Badgr client to fetch Badgr information. The client is tied to a
    specific access_token. All badge calls must have an issuer id.
    """

    def get_issuers(issuer_id):
        """
        Get the :class:`IBadgrIssuer` for this issuer id.
        """

    def get_issuers():
        """
        Get all :class:`IBadgrIssuer` objects.
        """

    def get_badge(badge_template_id):
        """
        Get the :class:`IBadgrBadge` associated with the template id.
        """

    def get_badges(sort=None, filters=None, page=None):
        """
        Return an :class:`IBadgrBadgeCollection`.

        https://www.yourbadgr.com/docs/badge_templates
        """

    def get_awarded_badges(user, sort=None, filters=None, page=None, public_only=None, accepted_only=False):
        """
        Return an :class:`IAwardedBadgrBadgeCollection`.

        public_only - only return public badges
        https://www.yourbadgr.com/docs/issued_badges filtered by user email.
        """

    def award_badge(user, badge_template_id, suppress_badge_notification_email=False,
                    locale=None, evidence_ntiid=None, evidence_title=None, evidence_desc=None):
        """
        Award a badge to a user.

        evidence_ntiid - ntiid of object awarding the badge
        evidence_title - evidence title
        evidence_desc - evidence description
        https://www.yourbadgr.com/docs/issued_badges
        """


class IBadgrBadge(IBadgrType):
    """
    An Badgr badge template.
    """

    issuer_entity_id = ValidTextLine(title=u'the badge issuer entity_id',
                                     min_length=1,
                                     required=True)

    issuer_open_badge_id = ValidTextLine(title=u'issuer open badge id',
                                         min_length=1,
                                         required=False)

    created_at = ValidDatetime(title=u"Badge created date",
                               required=True)


class IAwardedBadgrBadge(IBadgrType):

    badge_template = Object(IBadgrBadge,
                            title=u'The Badgr badge template.',
                            required=True)

    image_url = HTTPURL(title=u"Badge image url",
                        required=False)

    created_at = ValidDatetime(title=u"Badge created date",
                               required=True)

    updated_at = ValidDatetime(title=u"Badge last modified",
                               required=True)

    public = Bool(title=u"Badge is public",
                  required=True)

    locale = ValidTextLine(title=u"Badge user locale",
                           required=True)

    recipient_email = ValidTextLine(title=u"Badge user email",
                                    required=True)

    accept_badge_url = HTTPURL(title=u"Accept badge URL",
                               description=u"Should only have one of accept_badge_url or badge_url",
                               required=False)

    badge_url = HTTPURL(title=u"Badge URL",
                        description=u"Should only have one of accept_badge_url or badge_url",
                        required=False)

    state = ValidTextLine(title=u"Badge state",
                          description=u"State - pending, accepted, revoked, rejected",
                          required=False)

    evidence = ListOrTuple(Object(IBadgrEvidence),
                           title=u"Badgr awarded badge evidence",
                           required=True,
                           min_length=0)


class IBadgePageMetadata(interface.Interface):
    """
    Badge page metadata.
    """

    badges_count = Int(title=u"Badge count",
                       required=True)

    total_badges_count = Int(title=u"Total badges count",
                             required=False)

    current_page = Int(title=u"Current page",
                       required=True)

    total_pages = Int(title=u"Total page count",
                      required=True)


class IBadgrBadgeCollection(IBadgePageMetadata):

    Items = ListOrTuple(Object(IBadgrBadge),
                        title=u"Badgr badges",
                        required=True,
                        min_length=0)


class IAwardedBadgrBadgeCollection(IBadgePageMetadata):

    Items = ListOrTuple(Object(IAwardedBadgrBadge),
                        title=u"Awarded Badgr badges",
                        required=True,
                        min_length=0)


class IBadgrIssuerCollection(interface.Interface):

    issuers = ListOrTuple(Object(IBadgrIssuer),
                          title=u"Badgr issuers",
                          required=True,
                          min_length=0)


class BadgrClientError(Exception):

    def __init__(self, msg, json=None):
        Exception.__init__(self, msg)
        self.json = json


class InvalidBadgrIntegrationError(BadgrClientError):
    """
    Raised when an badgr integration is invalid, most likely an
    invalid authorization_token.
    """


class MissingBadgrOrganizationError(BadgrClientError):
    """
    Raised when an badgr integration is not tied to an organization.
    This should not happen. Integrations should only make API calls
    if persistent and tied to an organization.
    """


class DuplicateBadgrBadgeAwardedError(Exception):
    """
    Issued when a badge is awarded to a user, but the user has already
    been awarded the badge. This should only occur if the awarded badge
    is not configured for being awarded multiple times to a user.
    """
