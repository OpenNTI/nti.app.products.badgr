__import__('pkg_resources').declare_namespace(__name__)  # pragma: no cover


import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

BADGES = 'badges'

VIEW_AWARDED_BADGES = 'awarded_badges'

ENABLE_BADGR_VIEW = 'EnableBadgr'

BADGR_INTEGRATION_NAME = u'badgr'

NT_EVIDENCE_NTIID_ID = u'NextThoughtEvidenceNTIID'

REL_AUTH_BADGR = 'authorize.badgr'
