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

from nti.app.products.badgr.interfaces import IBadgrIntegration

from nti.app.products.badgr.model import BadgrIntegration

from nti.app.products.integration.interfaces import IIntegrationCollectionProvider

logger = __import__('logging').getLogger(__name__)


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
