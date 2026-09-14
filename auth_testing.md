# AHONIX Auth Testing Playbook

Unified auth: custom JWT (email/password) + Emergent Google OAuth. Canonical id = UUID `user_id`.

## Test account
- Email: alex@northstargoods.com  Password: Ahonix2026!  (already has a demo workspace)

## API testing
```
# login (JWT cookies)
curl -c cookies.txt -X POST https://<host>/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"alex@northstargoods.com","password":"Ahonix2026!"}'
curl -b cookies.txt https://<host>/api/auth/me
curl -b cookies.txt https://<host>/api/overview
```
Login returns the user object and sets access_token + refresh_token cookies.
/me returns the same user via those cookies. Protected endpoints 401 without cookies.

## Emergent Google session (for browser testing)
Create user + session directly:
```
mongosh --eval "
use('test_database');
var uid='user_'+Date.now();
var st='test_session_'+Date.now();
db.users.insertOne({user_id:uid,email:'g'+Date.now()+'@example.com',name:'Google Test',auth_provider:'google',onboarding_completed:false,active_workspace_id:null,created_at:new Date()});
db.user_sessions.insertOne({user_id:uid,session_token:st,expires_at:new Date(Date.now()+7*24*3600*1000),created_at:new Date()});
print('session_token '+st);"
```
Set cookie `session_token` in the browser, then load the app.

## Data isolation
Every /api/* data endpoint resolves the active workspace via the authed user and filters
workspaces by user_id. A user can never read another user's workspace.
