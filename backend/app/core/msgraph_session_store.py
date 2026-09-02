"""
In-memory M365 account-link state, shared between
app.api.v1.endpoints.msgraph (which populates it at OAuth callback
time) and app.services.msgraph_mail_sync_service (EPIC-14/S-435, which
reads it to know which users have a live Graph session to sync mail
for). Extracted into its own module so the service layer never has to
import from an endpoints module (the wrong direction) to reach this
import logging
state.

Same real limitation documented at the original definition site: this
is process-local in-memory storage, not persisted -- a server restart
clears every live token/link, same as any other in-memory "demo"
session store in this codebase. A real deployment would move this to
Redis/DB-backed storage; not built here, not this story's scope.
"""

# MS Graph OAuth token results, keyed by the Microsoft account's real
# oid (object id) -- see msgraph.py's /auth/callback.
user_tokens = {}

# Maps this app's Users.UserID to the MS Graph oid above, so a caller's
# own JWT identity (never a client-suppliable value) resolves to their
# linked Graph session -- see msgraph.py's _require_account() docstring
# for the real IDOR this was built to close.
account_id_by_user_id = {}
