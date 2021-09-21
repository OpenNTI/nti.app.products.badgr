#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: model.py 124702 2017-12-08 21:11:48Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.container.contained import Contained

from nti.app.products.badgr import BADGR_INTEGRATION_NAME

from nti.app.products.badgr.interfaces import IBadgrIntegration

from nti.app.products.integration.integration import AbstractIntegration

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.externalization.representation import WithRepr

from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


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
    mimeType = mime_type = "application/vnd.nextthought.site.badgrintegration"
