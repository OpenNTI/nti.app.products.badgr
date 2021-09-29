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

from zope.container.contained import Contained

from zope.intid.interfaces import IIntIds

from nti.app.products.integration.interfaces import IIntegrationCollectionProvider

from nti.app.products.integration.integration import AbstractIntegration
from nti.app.products.integration.integration import AbstractOAuthAuthorizedIntegration

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.app.products.badgr import BADGR_INTEGRATION_NAME

from nti.app.products.badgr.interfaces import IBadgrIntegration
from nti.app.products.badgr.interfaces import IBadgrAuthorizedIntegration

from nti.app.products.badgr.utils import get_auth_tokens

from nti.dataserver.interfaces import IRedisClient

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.externalization.internalization import update_from_external_object

from nti.externalization.representation import WithRepr

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured


@interface.implementer(IIntegrationCollectionProvider)
class BadgrIntegrationProvider(object):

    def can_integrate(self):
        #TODO: query site policy/license
        return True

    def get_collection_iter(self):
        """
        Return a BadgrIntegration object by which we can enable
        Badgr integration.
        """
        result = component.queryUtility(IBadgrIntegration)
        if result is None:
            result = BadgrIntegration(title=u'Integrate with Badgr')
        return (result,)


# Order of parent classes matters here
@WithRepr
@interface.implementer(IBadgrIntegration)
class BadgrIntegration(AbstractIntegration,
                       PersistentCreatedModDateTrackingObject,
                       Contained):

    __parent__ = None
    __name__ = BADGR_INTEGRATION_NAME

    title = u'Badgr Integration'

    createDirectFieldProperties(IBadgrIntegration)
    mimeType = mime_type = "application/vnd.nextthought.integration.badgrintegration"


@component.adapter(dict)
@interface.implementer(IBadgrAuthorizedIntegration)
def _auth_badgr_factory(access_data):
    """
    On successful authorization, we get a dict back of auth info.
    """
    obj = BadgrAuthorizedIntegration()
    update_from_external_object(obj, access_data)
    return obj


@WithRepr
@interface.implementer(IBadgrAuthorizedIntegration)
class BadgrAuthorizedIntegration(AbstractOAuthAuthorizedIntegration,
                                 PersistentCreatedAndModifiedTimeObject,
                                 SchemaConfigured):

    createDirectFieldProperties(IBadgrAuthorizedIntegration)

    __name__ = BADGR_INTEGRATION_NAME

    mimeType = mime_type = "application/vnd.nextthought.integration.badgrauthorizedintegration"
    title = u'Authorized Badgr Integration'

    lock_timeout = 60 * 3
    # 24 hours for access token
    access_token_expiry = 60 * 60 * 24
    # ? days for refresh token (assume 30 days)
    refresh_token_expiry = 60 * 60 * 24 * 30

    @property
    def _key_base_name(self):
        intids = component.getUtility(IIntIds)
        intid = intids.getId(self)
        return 'badgr/tokens/%s/%s' % (getSite().__name__, intid)

    @property
    def _access_token_key_name(self):
        return '%s/%s' % (self._key_base_name, 'access_token')

    @property
    def _refresh_token_key_name(self):
        return '%s/%s' % (self._key_base_name, 'refresh_token')

    def store_tokens(self, access_token, refresh_token):
        """
        Called after initialization or during update, stores the state of the
        tokens. This should only be called with appropriate safeguarding of
        concurrency.
        """
        self._redis_client.setex(self._access_token_key_name,
                                 time=self.access_token_expiry,
                                 value=access_token)
        self._redis_client.setex(self._refresh_token_key_name,
                                 time=self.refresh_token_expiry,
                                 value=refresh_token)

    @property
    def _redis_client(self):
        return component.getUtility(IRedisClient)

    @property
    def access_token(self):
        result = self._redis_client.get(self._access_token_key_name)
        if result is None:
            result = self.update_tokens()
        return result

    def get_access_token(self):
        return self.access_token

    @property
    def refresh_token(self):
        # This should never be None
        return self._redis_client.get(self._refresh_token_key_name)

    def get_refresh_token(self):
        return self.refresh_token

    @property
    def _lock(self):
        return self._redis_client.lock(self._key_base_name,
                                       self.lock_timeout)

    def update_tokens(self, old_access_token=None):
        with self._lock:
            # Someone may beat us; if so, use their new token
            current_access_token = self._redis_client.get(self._access_token_key_name)
            if     not current_access_token \
                or current_access_token == old_access_token:
                # First one here, update and store
                access_token, refresh_token = get_auth_tokens(self.refresh_token)
                self.store_tokens(access_token, refresh_token)
                result = access_token
            else:
                result = current_access_token
        return result