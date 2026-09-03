"""
EPIC-14/S-435 (HRMS-1408) -- Candidate & Employee Lifecycle
Communication Linking, mail half. No live Graph webhook subscription
exists in this codebase (that needs a public HTTPS validation endpoint
-- real, but heavier follow-up work), so this is a poll-based sync:
every linked user's inbox + sent items get pulled since their last
sync and passed through
lifecycle_communication_linking_service.link_email_to_lifecycle_record()
one message at a time. Message BODY is never fetched -- the Graph
$select below only ever requests subject/from/to/timestamps/webLink,
matching BR-1408-01 (metadata-only) at the source, not just at the
import logging
point of storage.

graph_call is injectable (same convention as
calendar_matching_service.get_interviewer_busy_events) so no test ever
hits a real Microsoft endpoint.
"""
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.user import Users
from app.services.lifecycle_communication_linking_service import link_email_to_lifecycle_record

GraphMessagesCall = Callable[[str, str], dict]

DEFAULT_LOOKBACK = timedelta(hours=24)
MAX_MESSAGES_PER_FOLDER = 50


def _default_graph_messages_call(access_token: str, endpoint: str) -> dict:
    import requests

    resp = requests.get(endpoint, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _fetch_messages(access_token: str, folder: str, since: datetime, *, graph_call: Optional[GraphMessagesCall] = None) -> list:
    call = graph_call or _default_graph_messages_call
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_field = "receivedDateTime" if folder == "inbox" else "sentDateTime"
    endpoint = (
        f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages"
        f"?$filter={date_field} ge {since_iso}"
        f"&$select=subject,from,toRecipients,receivedDateTime,sentDateTime,webLink"
        f"&$top={MAX_MESSAGES_PER_FOLDER}"
        f"&$orderby={date_field}"
    )
    data = call(access_token, endpoint)
    return data.get("value", [])


def _parse_graph_datetime(raw: Optional[str]) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


def sync_mail_for_user(
    db: Session, user: Users, access_token: str, *,
    graph_call: Optional[GraphMessagesCall] = None, now: Optional[datetime] = None,
) -> dict:
    """Fetches this user's mail since their last sync (or a 24h default
    lookback on the first run), links each message that matches a
    verified candidate/employee address, and advances the high-water
    mark -- but only on a successful fetch, so a transient Graph/auth
    failure retries the same window next run instead of silently
    skipping it. Never raises."""
    now = now or datetime.utcnow()
    since = user.msgraph_mail_last_synced_at or (now - DEFAULT_LOOKBACK)

    linked_count = 0
    try:
        for message in _fetch_messages(access_token, "inbox", since, graph_call=graph_call):
            sender = (message.get("from") or {}).get("emailAddress", {}).get("address")
            if link_email_to_lifecycle_record(
                db, other_party_email=sender, direction="RECEIVED",
                subject=message.get("subject"),
                timestamp=_parse_graph_datetime(message.get("receivedDateTime")),
                web_link=message.get("webLink"), tenant_id=user.tenant_id, actor_id=user.UserID,
            ):
                linked_count += 1

        for message in _fetch_messages(access_token, "sentitems", since, graph_call=graph_call):
            for recipient in message.get("toRecipients") or []:
                address = (recipient.get("emailAddress") or {}).get("address")
                if link_email_to_lifecycle_record(
                    db, other_party_email=address, direction="SENT",
                    subject=message.get("subject"),
                    timestamp=_parse_graph_datetime(message.get("sentDateTime")),
                    web_link=message.get("webLink"), tenant_id=user.tenant_id, actor_id=user.UserID,
                ):
                    linked_count += 1
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[MsgraphMailSync] Failed to sync mail for user {user.UserID}: {exc}")
        return {"linked": linked_count, "synced": False}

    user.msgraph_mail_last_synced_at = now
    db.add(user)
    db.commit()
    return {"linked": linked_count, "synced": True}


def run_msgraph_mail_sync_job(db: Session) -> dict:
    """Runs on a schedule (see app.core.scheduler) -- iterates every
    user with a currently-live linked M365 session and syncs each.
    Never raises; per-user failures are isolated so one broken/expired
    token can't block everyone else's sync."""
    from app.core.msgraph_session_store import account_id_by_user_id, user_tokens

    synced_users = 0
    total_linked = 0
    for user_id, account_id in list(account_id_by_user_id.items()):
        token_data = user_tokens.get(account_id)
        if not token_data or "access_token" not in token_data:
            continue
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            continue
        try:
            result = sync_mail_for_user(db, user, token_data["access_token"])
            if result["synced"]:
                synced_users += 1
                total_linked += result["linked"]
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[MsgraphMailSync] Unexpected error syncing user {user_id}: {exc}")

    return {"synced_users": synced_users, "total_linked": total_linked}
