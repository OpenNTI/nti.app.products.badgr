#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: model.py 123306 2017-10-19 03:47:14Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import base64
import requests

import pyramid.httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from zope import component

from nti.app.externalization.error import raise_json_error

from nti.app.products.badgr import MessageFactory as _

from nti.common.interfaces import IOAuthKeys

logger = __import__('logging').getLogger(__name__)


BADGR_AUTH_TOKEN_URL = "https://api.badgr.io/o/token"


def raise_error(data, tb=None, factory=hexc.HTTPBadRequest, request=None):
    request = request or get_current_request()
    raise_json_error(request, factory, data, tb)


def get_token_data(post_data):
    """
    Get the badgr token data, using the supplied post_data dict
    for the certain type of token fetch.
    """
    auth_keys = component.getUtility(IOAuthKeys, name="badgr")
    auth_header = '%s:%s' % (auth_keys.APIKey, auth_keys.secretKey)
    auth_header = base64.b64encode(auth_header)
    auth_header = 'Basic %s' % auth_header
    response = requests.post(BADGR_AUTH_TOKEN_URL,
                             post_data,
                             headers={'Authorization': auth_header})
    if response.status_code != 200:
        error_json = response.json()
        if 'error' in error_json and error_json['error'] == 'invalid_grant':
            # This is likely a lapsed account that will need to be re-authorized.
            logger.warn('Invalid grant while getting badgr token, may need to be re-authorized (%s)',
                        response.text)
            raise_error({'message': _(u"Error during badgr auth, may need to re-authorize."),
                         'code': 'BadgrInvalidAuthError'})
        else:
            logger.warn('Error while getting badgr token (%s)',
                        response.text)
            raise_error({'message': _(u"Error during badgr auth."),
                         'code': 'BadgrAuthError'})

    access_data = response.json()
    if 'access_token' not in access_data:
        logger.warn('Missing badgr access token (%s)',
                    access_data)
        raise_error({'message': _(u"No badgr access token"),
                     'code': 'BadgrAuthMissingAccessToken'})
    if 'refresh_token' not in access_data:
        logger.warn('Missing badgr refresh token (%s)',
                    access_data)
        raise_error({'message': _(u"No badgr refresh token"),
                     'code': 'BadgrAuthMissingRefreshToken'})
    if not access_data.get('refresh_token'):
        # Not sure how this could happen
        logger.warn("Received an empty refresh token? (%s) (%s) (%s)",
                    post_data, access_data, response.status_code)
        raise_error({'message': _(u"No badgr refresh token"),
                     'code': 'BadgrAuthMissingRefreshToken'})
    return access_data


def get_auth_tokens(refresh_token):
    """
    Fetch an access_token and refresh_token
    """
    data = {'refresh_token': refresh_token,
            'grant_type': 'refresh_token'}
    access_data = get_token_data(data)
    return access_data.get('access_token'), access_data.get('refresh_token')
