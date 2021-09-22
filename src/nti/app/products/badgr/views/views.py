#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.badgr import BADGES
from nti.app.products.badgr import ENABLE_BADGR_VIEW
from nti.app.products.badgr import VIEW_AWARDED_BADGES

from nti.app.products.badgr import MessageFactory as _

from nti.app.products.badgr.authorization import ACT_BADGR

from nti.app.products.badgr.interfaces import IBadgrBadge
from nti.app.products.badgr.interfaces import IBadgrClient
from nti.app.products.badgr.interfaces import BadgrClientError
from nti.app.products.badgr.interfaces import IBadgrIntegration
from nti.app.products.badgr.interfaces import IBadgrInitializationUtility
from nti.app.products.badgr.interfaces import InvalidBadgrIntegrationError

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IHostPolicyFolder

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.links.links import Link

from nti.site.utils import unregisterUtility

logger = __import__('logging').getLogger(__name__)

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
LINKS = StandardExternalFields.LINKS
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


def raise_error(data, tb=None,
                factory=hexc.HTTPUnprocessableEntity,
                request=None):
    raise_json_error(request, factory, data, tb)


class BadgrIntegrationUpdateMixin(object):

    @Lazy
    def site(self):
        return getSite()

    @Lazy
    def site_manager(self):
        return self.site.getSiteManager()

    def _unregister_integration(self):
        registry = component.getSiteManager()
        unregisterUtility(registry, provided=IBadgrIntegration)

    def set_organization(self, integration):
        """
        Fetch organizations, which should be a single entry. This should be
        called every time the authorization token is updated.

        Raises :class:`InvalidBadgrIntegrationError` if token is invalid.
        """
        intialization_utility = component.getUtility(IBadgrInitializationUtility)
        try:
            intialization_utility.initialize(integration)
        except InvalidBadgrIntegrationError:
            raise_error({'message': _(u"Invalid Badgr authorization_token."),
                         'code': 'InvalidBadgrAuthorizationTokenError'})
        return integration


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IHostPolicyFolder,
             request_method='POST',
             name=ENABLE_BADGR_VIEW,
             permission=ACT_BADGR)
class EnableBadgrIntegrationView(AbstractAuthenticatedView,
                                 ModeledContentUploadRequestUtilsMixin,
                                 BadgrIntegrationUpdateMixin):
    """
    Enable the badgr integration
    """

    DEFAULT_FACTORY_MIMETYPE = "application/vnd.nextthought.badgrintegration"

    def readInput(self, value=None):
        if self.request.body:
            values = super(EnableBadgrIntegrationView, self).readInput(value)
        else:
            values = self.request.params
        values = dict(values)
        # Can't be CaseInsensitive with internalization
        if MIMETYPE not in values:
            values[MIMETYPE] = self.DEFAULT_FACTORY_MIMETYPE
        return values

    def _do_call(self):
        logger.info("Integration badgr for site (%s) (%s)",
                    self.site.__name__, self.remoteUser)
        # XXX: The usual "what do we do" for parent and child site questions here.
        if component.queryUtility(IBadgrIntegration):
            raise_error({'message': _(u"Badgr integration already exists"),
                         'code': 'ExistingBadgrIntegrationError'})
        integration = self.readCreateUpdateContentObject(self.remoteUser)
        result = self.set_organization(integration)
        return result


@view_config(route_name='objects.generic.traversal',
             context=IBadgrIntegration,
             request_method='PUT',
             permission=ACT_BADGR,
             renderer='rest')
class BadgrIntegrationPutView(UGDPutView,
                              BadgrIntegrationUpdateMixin):

    def updateContentObject(self, obj, externalValue):
        super(BadgrIntegrationPutView, self).updateContentObject(obj, externalValue)
        # If changing authorization token, refresh organization.
        if 'authorization_token' in externalValue:
            self.set_organization(obj)
        return obj


@view_config(route_name='objects.generic.traversal',
             context=IBadgrIntegration,
             request_method='DELETE',
             permission=ACT_BADGR,
             renderer='rest')
class BadgrIntegrationDeleteView(AbstractAuthenticatedView,
                                   BadgrIntegrationUpdateMixin):
    """
    Allow deleting (unauthorizing) a :class:`IBadgrIntegration`.
    """

    def __call__(self):
        try:
            del self.site_manager[self.context.__name__]
        except KeyError:
            pass
        self._unregister_integration()
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             context=IBadgrIntegration,
             request_method='GET',
             permission=ACT_BADGR,
             name='organizations',
             renderer='rest')
class BadgrIntegrationOrganizationsView(AbstractAuthenticatedView):

    def __call__(self):
        result = LocatedExternalDict()
        client = IBadgrClient(self.context)
        try:
            organizations = client.get_organizations()
        except BadgrClientError:
                raise_error({'message': _(u"Error during integration."),
                             'code': 'BadgrClientError'})
        result[ITEMS] = items = organizations
        result[ITEM_COUNT] = result[TOTAL] = len(items)
        return result


@view_config(route_name='objects.generic.traversal',
             context=IBadgrIntegration,
             request_method='GET',
             permission=ACT_BADGR,
             renderer='rest')
class BadgrIntegrationGetView(GenericGetView):
    pass


@view_config(route_name='objects.generic.traversal',
             context=IBadgrBadge,
             request_method='DELETE',
             permission=ACT_CONTENT_EDIT,
             renderer='rest')
class BadgrBadgeDeleteView(UGDDeleteView):
    """
    Allow deleting a :class:`IBadgrBadge`.
    """

    def __call__(self):
        try:
            del self.context.__parent__[self.context.__name__]
        except KeyError:
            pass
        return hexc.HTTPNoContent()


class AbstractBadgrAPIView(AbstractAuthenticatedView):
    """
    Supply batch-next, batch-prev rels if necessary.
    """

    DEFAULT_SORT_PARAM = None

    NAME_FILTER_KEY = 'name'

    @Lazy
    def _params(self):
        return CaseInsensitiveDict(self.request.params)

    @property
    def page(self):
        return self._params.get('page')

    @property
    def filter(self):
        # Only filter on name currently
        filter_str = self._params.get('filter')
        if filter_str:
            return {self.NAME_FILTER_KEY: filter_str}

    @property
    def sort(self):
        result = self._params.get('sort', self.DEFAULT_SORT_PARAM)
        result = result.split(',')
        return result

    def _decorate_batch_rels(self, badgr_collection, ext):
        batch_params = self.request.GET.copy()
        batch_params.pop('page', None)
        links = ext.setdefault(LINKS, [])
        if badgr_collection.current_page > 1:
            prev_batch_params = dict(batch_params)
            prev_batch_params['page'] = badgr_collection.current_page - 1
            link = Link(self.request.path,
                        rel='batch-prev',
                        params=prev_batch_params)
            links.append(link)
        if badgr_collection.current_page < badgr_collection.total_pages:
            next_batch_params = dict(batch_params)
            next_batch_params['page'] = badgr_collection.current_page + 1
            link = Link(self.request.path,
                        rel='batch-next',
                        params=next_batch_params)
            links.append(link)
        return ext

    def __call__(self):
        badgr_collection = self._do_call()
        result = to_external_object(badgr_collection)
        # Create `page` batch rels
        result = self._decorate_batch_rels(badgr_collection, result)
        return result


@view_config(route_name='objects.generic.traversal',
             context=IBadgrIntegration,
             request_method='GET',
             name=BADGES,
             permission=ACT_CONTENT_EDIT,
             renderer='rest')
class BadgrBadgesView(AbstractBadgrAPIView):
    """
    Get all badges from this badgr account

    sort - {badges_count, created_at, name, updated_at}
    """

    DEFAULT_SORT_PARAM = 'name'

    def _do_call(self):
        client = IBadgrClient(self.context)
        try:
            collection = client.get_badges(sort=self.sort,
                                           filters=self.filter,
                                           page=self.page)
        except BadgrClientError:
            raise_error({'message': _(u"Error while getting badge templates."),
                         'code': 'BadgrClientError'})
        return collection


@view_config(route_name='objects.generic.traversal',
             context=IUser,
             request_method='GET',
             name=VIEW_AWARDED_BADGES,
             permission=ACT_READ,
             renderer='rest')
class UserAwardedBadgesView(AbstractBadgrAPIView):
    """
    Get all awarded badges for this user.

    Other parties will only be able to see public badges.

    sort - {created_at, issued_at, state_updated_at, badge_templates[name]}
    """

    # Issued at in desc order ('-' is descending)
    DEFAULT_SORT_PARAM = '-issued_at'

    NAME_FILTER_KEY = 'badge_templates[name]'

    def _do_call(self):
        accepted_only = public_only = self.remoteUser != self.context
        integration = component.queryUtility(IBadgrIntegration)
        if not integration:
            raise hexc.HTTPNotFound()
        client = IBadgrClient(integration)
        try:
            collection = client.get_awarded_badges(self.context,
                                                   sort=self.sort,
                                                   filters=self.filter,
                                                   page=self.page,
                                                   public_only=public_only,
                                                   accepted_only=accepted_only)
        except BadgrClientError:
            raise_error({'message': _(u"Error while getting issued badges."),
                         'code': 'BadgrClientError'})
        return collection
