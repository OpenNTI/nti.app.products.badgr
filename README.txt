Mothballed on Sept 29, 2021


https://badgr.org/app-developers/#oauth2

https://api.badgr.io/docs/v2

http://localhost:8082/dataserver2/users/josh.zuech@nextthought.com/Integration/Integrations/badgr/@@authorize.badgr

Current state
* IPython breakpoints in the code
* oauth2 not fully working 
* internalization/client API only partially complete

Setup info
* badgr source code in buildout cfgs
* move courseware/acclaim to courseware/badges/acclaim and courseware/badges/badgr 
* bring back nti.app.products.badges for common interfaces
* course badges collection can be either acclaim/credly, badgr, or both (We ignore non-integrated?)
* buildout cfg oauth keys
* buildout cfg oauth service (to route redirects, since we cannot have a redirect uri configured for each client)
* intergration -> authorized integration (via authorize endpoint)
* access/refresh tokens - need methed to periodically refresh these so they dont go stale (cronjob, somethinng else)
** see webinar methodology
** tokens stored in redis
* auth_integration adapts to client to make API calls
* hooks to award badges (what if have credly and badgr in course collection)
* assuming one issuer (org in credly) per authorized account
* plan was to only have one badge integration (badgr or credly) to simplify things

awarded badges for user (distinct per impl)
- credly
- badgr

tie badges to course (distinct per api) (course API supports either)
- credly
- badgr

badgr
- passwords
- config
- dev config
- badgr intergration
- badgr oauth2
- badgr refresh cronjob (?) (webinar)
- badgr client
- badgr tests