#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.component.hooks import getSite

from zope.container.interfaces import ILocation

from nti.app.products.badgr import BADGES
from nti.app.products.badgr import ENABLE_BADGR_VIEW
from nti.app.products.badgr import VIEW_AWARDED_BADGES

from nti.app.products.badgr.authorization import ACT_BADGR

from nti.app.products.badgr.interfaces import IBadgrBadge
from nti.app.products.badgr.interfaces import IAwardedBadgrBadge
from nti.app.products.badgr.interfaces import IBadgePageMetadata
from nti.app.products.badgr.interfaces import IBadgrIntegration

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.interfaces import IUser

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


def located_link(parent, link):
    interface.alsoProvides(link, ILocation)
    link.__name__ = ''
    link.__parent__ = parent
    return link


@component.adapter(IBadgrIntegration)
@interface.implementer(IExternalMappingDecorator)
class _BadgrEnableIntegrationDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        current_site = getSite()
        return super(_BadgrEnableIntegrationDecorator, self)._predicate(context, unused_result) \
           and has_permission(ACT_BADGR, current_site, self.request) \
           and not context.authorization_token

    def _do_decorate_external(self, unused_context, result):
        links = result.setdefault(LINKS, [])
        link_context = getSite()
        link = Link(link_context,
                    elements=("@@" + ENABLE_BADGR_VIEW,),
                    rel='enable')
        links.append(located_link(link_context, link))


@component.adapter(IBadgrIntegration)
@interface.implementer(IExternalMappingDecorator)
class _BadgrIntegrationDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _obscure_authorization_token(self, token):
        """
        Return first 3/4 of token as astericks.
        """
        token_len = len(token)
        segment_len = int(token_len / 4)
        prefix_len = segment_len * 3
        prefix = '*' * prefix_len
        suffix = token[prefix_len:]
        return '%s%s' % (prefix, suffix)

    def _do_decorate_external(self, context, result):
        if context.authorization_token:
            result['authorization_token'] = self._obscure_authorization_token(context.authorization_token)
        links = result.setdefault(LINKS, [])
        if has_permission(ACT_BADGR, context, self.request):
            link = Link(context,
                        rel='disconnect',
                        method='DELETE')
            links.append(located_link(context, link))

        if has_permission(ACT_CONTENT_EDIT, context, self.request):
            link = Link(context,
                        rel='badges',
                        elements=(BADGES,))
            links.append(located_link(context, link))


@component.adapter(IUser)
@interface.implementer(IExternalMappingDecorator)
class _UserBadgesLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Expose awarded badges for this user and any who can READ this user, which
    is typically everyone.
    """

    def _predicate(self, context, unused_result):
        return component.queryUtility(IBadgrIntegration) is not None \
            and has_permission(ACT_READ, context)

    def _do_decorate_external(self, context, mapping):
        _links = mapping.setdefault(LINKS, [])
        _links.append(Link(context,
                           elements=(VIEW_AWARDED_BADGES,),
                           rel=VIEW_AWARDED_BADGES))


@component.adapter(IBadgrBadge)
@interface.implementer(IExternalMappingDecorator)
class _BadgeDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        return component.queryUtility(IBadgrIntegration) is not None

    def _do_decorate_external(self, context, mapping):
        integration = component.queryUtility(IBadgrIntegration)
        current_organization_id = getattr(integration.organization, 'organization_id', None)
        mapping['InvalidOrganization'] =   not current_organization_id \
                                        or context.organization_id != current_organization_id


@component.adapter(IAwardedBadgrBadge)
@interface.implementer(IExternalObjectDecorator)
class _BadgrAwardedBadgeDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        return context.User != self.remoteUser

    def _do_decorate_external(self, unused_context, mapping):
        mapping.pop('accept_badge_url', None)
        mapping.pop('badge_url', None)


@component.adapter(IBadgePageMetadata)
@interface.implementer(IExternalMappingDecorator)
class _BadgePageDecorator(Singleton):
    """
    BadgePageDecorator to map items.
    """

    def decorateExternalMapping(self, context, mapping):
        mapping[ITEM_COUNT] = context.badges_count
        mapping[TOTAL] = context.total_badges_count
