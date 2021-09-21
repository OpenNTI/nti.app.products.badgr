#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: model.py 123306 2017-10-19 03:47:14Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.container.contained import Contained

from nti.app.products.badgr import NT_EVIDENCE_NTIID_ID

from nti.app.products.badgr.interfaces import IBadgrBadge
from nti.app.products.badgr.interfaces import IBadgrIdEvidence
from nti.app.products.badgr.interfaces import IBadgrOrganization
from nti.app.products.badgr.interfaces import IAwardedBadgrBadge
from nti.app.products.badgr.interfaces import IBadgrBadgeCollection
from nti.app.products.badgr.interfaces import IBadgrOrganizationCollection
from nti.app.products.badgr.interfaces import IAwardedBadgrBadgeCollection

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.externalization.internalization import update_from_external_object

from nti.externalization.representation import WithRepr

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.ntiids.oids import to_external_ntiid_oid

from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)


@component.adapter(dict)
@interface.implementer(IBadgrIdEvidence)
def _badgr_id_evidence_factory(ext):
    ext['ntiid'] = ext.get('id')
    obj = BadgrIdEvidence()
    update_from_external_object(obj, ext)
    return obj


@component.adapter(dict)
@interface.implementer(IBadgrOrganization)
def _badgr_organization_factory(ext):
    if 'data' in ext:
        ext = ext['data']
    obj = BadgrOrganization()
    ext['organization_id'] = ext['id']
    update_from_external_object(obj, ext)
    return obj


@component.adapter(dict)
@interface.implementer(IBadgrBadge)
def _badgr_badge_factory(ext):
    if 'data' in ext:
        ext = ext['data']
    obj = BadgrBadge()
    if 'owner' in ext:
        ext['organization_id'] = ext['owner'].get('id')
        ext['organization_name'] = ext['owner'].get('name')
    ext['badge_url'] = ext.pop('url')
    ext['template_id'] = ext['id']
    update_from_external_object(obj, ext)
    return obj


@component.adapter(dict)
@interface.implementer(IAwardedBadgrBadge)
def _awarded_badgr_badge_factory(ext):
    if 'data' in ext:
        ext = ext['data']
    ext['badge_template'] = IBadgrBadge(ext['badge_template'])
    if 'evidence' in ext:
        # Only concerning ourselves with NT evidence
        evidence = ext['evidence'] or []
        new_evidence = []
        for evi in evidence:
            if      evi.get('name') == NT_EVIDENCE_NTIID_ID \
                and is_valid_ntiid_string(evi.get('id')):
                new_evidence.append(IBadgrIdEvidence(evi))
        ext['evidence'] = new_evidence
    obj = AwardedBadgrBadge()
    update_from_external_object(obj, ext)
    return obj


@component.adapter(dict)
@interface.implementer(IBadgrBadgeCollection)
def _badgr_badge_collection_factory(ext):
    obj = BadgrBadgeCollection()
    metadata = ext['metadata']
    new_ext = dict()
    new_ext['Items'] = [IBadgrBadge(x) for x in ext['data']]
    new_ext['badges_count'] = metadata.get('count')
    new_ext['total_badges_count'] = metadata.get('total_count')
    new_ext['current_page'] = metadata.get('current_page')
    new_ext['total_pages'] = metadata.get('total_pages')
    update_from_external_object(obj, new_ext)
    return obj


@component.adapter(dict)
@interface.implementer(IAwardedBadgrBadgeCollection)
def _awarded_badgr_badge_collection_factory(ext):
    obj = AwardedBadgrBadgeCollection()
    metadata = ext['metadata']
    new_ext = dict()
    new_ext['Items'] = [IAwardedBadgrBadge(x) for x in ext['data']]
    new_ext['badges_count'] = metadata.get('count')
    new_ext['total_badges_count'] = metadata.get('total_count')
    new_ext['current_page'] = metadata.get('current_page')
    new_ext['total_pages'] = metadata.get('total_pages')
    update_from_external_object(obj, new_ext)
    return obj


@component.adapter(dict)
@interface.implementer(IBadgrOrganizationCollection)
def _badgr_organization_collection_factory(ext):
    obj = BadgrOrganizationCollection()
    new_ext = dict()
    new_ext['organizations'] = [IBadgrOrganization(x) for x in ext['data']]
    update_from_external_object(obj, new_ext)
    return obj


@WithRepr
@interface.implementer(IBadgrOrganization)
class BadgrOrganization(PersistentCreatedAndModifiedTimeObject,
                          Contained,
                          SchemaConfigured):
    createDirectFieldProperties(IBadgrOrganization)

    __parent__ = None
    __name__ = None

    mimeType = mime_type = "application/vnd.nextthought.badgr.organization"


@WithRepr
@EqHash('template_id')
@interface.implementer(IBadgrBadge, IAttributeAnnotatable)
class BadgrBadge(PersistentCreatedAndModifiedTimeObject,
                   Contained,
                   SchemaConfigured):

    createDirectFieldProperties(IBadgrBadge)

    mimeType = mime_type = "application/vnd.nextthought.badgr.badge"

    __name__ = None
    __parent__ = None

    @property
    def ntiid(self):
        # Let's us be linkable
        return to_external_ntiid_oid(self)


@WithRepr
@interface.implementer(IAwardedBadgrBadge)
class AwardedBadgrBadge(SchemaConfigured):

    createDirectFieldProperties(IAwardedBadgrBadge)

    mimeType = mime_type = "application/vnd.nextthought.badgr.awardedbadge"


@interface.implementer(IBadgrBadgeCollection)
class BadgrBadgeCollection(SchemaConfigured):

    createDirectFieldProperties(IBadgrBadgeCollection)

    mimeType = mime_type = "application/vnd.nextthought.badgr.badgecollection"

    badges = alias('Items')


@interface.implementer(IAwardedBadgrBadgeCollection)
class AwardedBadgrBadgeCollection(SchemaConfigured):

    createDirectFieldProperties(IAwardedBadgrBadgeCollection)

    mimeType = mime_type = "application/vnd.nextthought.badgr.awardedbadgecollection"

    badges = alias('Items')


@interface.implementer(IBadgrOrganizationCollection)
class BadgrOrganizationCollection(SchemaConfigured):

    createDirectFieldProperties(IBadgrOrganizationCollection)

    mimeType = mime_type = "application/vnd.nextthought.badgr.organizationcollection"


@interface.implementer(IBadgrIdEvidence)
class BadgrIdEvidence(SchemaConfigured):

    createDirectFieldProperties(IBadgrIdEvidence)

    mimeType = mime_type = "application/vnd.nextthought.badgr.idevidence"

    id = alias('ntiid')

    type = u'IdEvidence'
