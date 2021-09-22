#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import hashlib

from six.moves import urllib_parse

from zope import component

from zope.cachedescriptors.property import Lazy

import pyramid.httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.products.badgr import REL_AUTH_BADGR

from nti.app.products.badgr.interfaces import IBadgrIntegration
from nti.app.products.badgr.interfaces import IBadgrAuthorizedIntegration

from nti.app.products.badgr import MessageFactory as _

from nti.app.products.badgr.utils import get_token_data

from nti.common.interfaces import IOAuthKeys
from nti.common.interfaces import IOAuthService

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.intid.common import add_intid

from nti.links.externalization import render_link

from nti.links.links import Link

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

logger = __import__('logging').getLogger(__name__)

AUTH_BADGR_OAUTH2 = 'authorize.badgr.oauth2'


def raise_error(data, tb=None, factory=hexc.HTTPBadRequest, request=None):
    request = request or get_current_request()
    failure_redirect = request.session.get('badgr.failure')
    if failure_redirect:
        error_message = data.get('message')
        if error_message:
            parsed = urllib_parse.urlparse(failure_redirect)
            parsed = list(parsed)
            query = parsed[4]
            if query:
                query = query + '&error=' + urllib_parse.quote(error_message)
            else:
                query = 'error=' + urllib_parse.quote(error_message)
            parsed[4] = query
            failure_redirect = urllib_parse.urlunparse(parsed)
        raise hexc.HTTPSeeOther(location=failure_redirect)
    raise_json_error(request, factory, data, tb)


def redirect_badgr_oauth2_uri(request):
    link = Link(request.context, elements=(AUTH_BADGR_OAUTH2,))
    link = render_link(link)
    link_href = link.get('href')
    result = urllib_parse.urljoin(request.host_url, link_href)
    return result


@view_config(route_name='objects.generic.traversal',
             context=IBadgrIntegration,
             renderer='rest',
             request_method='GET',
             permission=ACT_CONTENT_EDIT,
             name=REL_AUTH_BADGR)
class BadgrAuth(AbstractAuthenticatedView):
    """
    The first step in the badgr auth flow.

    See: https://badgr.org/app-developers/

    ex:
        https://badgr.io/auth/oauth2/authorize?
        client_id=123
        &redirect_uri=https://example.com/auth
        &scope=r:profile rw:issuer r:backpack
    """

    @Lazy
    def oauth_keys(self):
        return component.getUtility(IOAuthKeys, name="badgr")

    @Lazy
    def nti_client_secret(self):
        return self.oauth_keys.ClientSecret

    @Lazy
    def nti_client_id(self):
        return self.oauth_keys.ClientId

    def __call__(self):
        request = self.request

        # Redirect
        auth_svc = component.getUtility(IOAuthService, name="badgr")
        auth_keys = component.getUtility(IOAuthKeys, name="badgr")
        state = hashlib.sha256(os.urandom(1024)).hexdigest()
        target = auth_svc.authorization_request_uri(
            client_id=auth_keys.APIKey,
            response_type="code",
            scope="rw:issuer r:backpack",
            state=state,
            redirect_uri=self._badgr_redirect_uri(),
        )
        
        for key in ('success', 'failure'):
            value = request.params.get(key)
            if value:
                request.session['badgr.' + key] = value

        # save state for validation
        request.session['badgr.state'] = state
        response = hexc.HTTPSeeOther(location=target)
        return response


@view_config(route_name='objects.generic.traversal',
             context=IBadgrIntegration,
             renderer='rest',
             request_method='GET',
             permission=ACT_CONTENT_EDIT,
             name=AUTH_BADGR_OAUTH2)
class BadgrAuth2(AbstractAuthenticatedView):
    """
    The second step in the badgr auth process.

    curl https://api.badgr.io/o/token -d \
        "grant_type=authorization_code\
        &code=XYZ\
        &client_id=123\
        &client_secret=ABC\
        &redirect_uri=https://example.com/auth"
    

    The access_token will expire in 1 day.
    
    curl https://api.badgr.io/o/token \
    -d "grant_type=authorization_code&code=authorization_code"

    Example token response:

    {
    "token_type": "Bearer",
    "access_token": "C1HePsbwS3tUmwC6OCKsC41w96xckc",
    "expires_in": 86400,
    "refresh_token": "xwHPFwH55tQpCy3qCgsIW59k3g3aPh",
    "scope": "rw:issuer rw:profile rw:backpack"
    }
    """

    def _create_auth_integration(self, access_data):
        auth_integration = IBadgrAuthorizedIntegration(access_data)
        auth_integration.creator = self.remoteUser.username
        # Lineage through registry
        auth_integration.__parent__ = component.getSiteManager()
        unregisterUtility(component.getSiteManager(), provided=IBadgrAuthorizedIntegration)
        registerUtility(component.getSiteManager(),
                        component=auth_integration,
                        provided=IBadgrAuthorizedIntegration)
        add_intid(auth_integration)
        auth_integration.store_tokens(access_data['access_token'],
                                      access_data['refresh_token'])
        return auth_integration

    def __call__(self):
        request = self.request
        params = request.params

        # check for errors
        if 'error' in params or 'errorCode' in params:
            error = params.get('error') or params.get('errorCode')
            logger.warn('Error code on badgr auth (%s)', error)
            raise_error({'message': _(u"Error code on badgr auth."),
                         'code': 'BadgrAuthErrorCode'})

        # Confirm code
        if 'code' not in params:
            logger.warn('No code on badgr auth (%s)', params)
            raise_error({'message': _(u"No code on badgr auth."),
                         'code': 'BadgrAuthMissingCode'})
        code = params.get('code')

        # Confirm anti-forgery state token
        if 'state' not in params:
            logger.warn('No state on badgr auth (%s)', params)
            raise_error({'message': _(u"No state on badgr auth."),
                         'code': 'BadgrAuthMissingStateParam'})
        params_state = params.get('state')
        session_state = request.session.get('badgr.state')
        if params_state != session_state:
            logger.warn('Invalid state on badgr auth (%s) (%s)',
                        params_state, session_state)
            raise_error({'message': _(u"Invalid state on badgr auth."),
                         'code': 'BadgrAuthInvalidStateParam'})

        # Exchange code for access and refresh token
        auth_keys = component.getUtility(IOAuthKeys, name="badgr")
        try:
            data = {'code': code,
                    'grant_type': 'authorization_code',
                    'client_id': auth_keys.APIKey,
                    'client_secret': auth_keys.SecretKey,
                    'redirect_uri': redirect_badgr_oauth2_uri(request)}
            access_data = get_token_data(data)
            auth_integration = self._create_auth_integration(access_data)
            request.environ['nti.request_had_transaction_side_effects'] = 'True'
        except Exception:
            logger.exception('Failed to authorize with badgr')
            raise_error({'message': _(u"Error during badgr authorization."),
                        'code': 'BadgrAuthError'})

        target = request.session.get('badgr.success')
        if target:
            response = hexc.HTTPSeeOther(location=target)
        else:
            response = auth_integration
        return response
