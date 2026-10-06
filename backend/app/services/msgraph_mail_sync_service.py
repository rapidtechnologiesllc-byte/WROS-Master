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
MAX_MESSAGES_PER_FOLDER = 50  # page size
MAX_PAGES_PER_FOLDER = 40  # up to 2,000 messages per folder per run

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
        f"&$select=subject,from,toRecipients,receivedDateTime,sentDateTime,webLink,bodyPreview"
        f"&$top={MAX_MESSAGES_PER_FOLDER}"
        f"&$orderby={date_field}"
    )
    messages = []
    for _ in range(MAX_PAGES_PER_FOLDER):
        data = call(access_token, endpoint)
        messages.extend(data.get("value", []))
        endpoint = data.get("@odata.nextLink")
        if not endpoint:
            break
    return messages

def _parse_graph_datetime(raw: Optional[str]) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()

def _link_one(db: Session, user: Users, **kwargs) -> Optional[dict]:
    """Link one message; a failure is logged and skipped so one bad
    message can't stall this mailbox's sync forever."""
    try:
        return link_email_to_lifecycle_record(db, tenant_id=user.tenant_id, actor_id=user.UserID, **kwargs)
    except Exception as exc:
        logger.error(f"[MsgraphMailSync] Could not link message for {user.UserID}: {exc}", exc_info=True)
        db.rollback()
        return None


def sync_mail_for_user(
    db: Session, user: Users, access_token: str, *,
    graph_call: Optional[GraphMessagesCall] = None, now: Optional[datetime] = None,
) -> dict:
    """Fetches this user's mail since their last sync (or a 24h default
    lookback on the first run), links each message whose other party is
    a known candidate/employee address, and advances the high-water mark
    -- only after a successful fetch, so a Graph/auth failure retries the
    same window next run. Never raises."""
    from app.core.msgraph_session_store import record_mail_access

    now = now or datetime.utcnow()
    since = user.msgraph_mail_last_synced_at or (now - DEFAULT_LOOKBACK)

    linked_count = 0
    inbound_linked = []
    try:
        inbox = _fetch_messages(access_token, "inbox", since, graph_call=graph_call)
        sent = _fetch_messages(access_token, "sentitems", since, graph_call=graph_call)
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        reason = ("Outlook mail access was not granted (Mail.Read). Ask the Azure admin to add it, then reconnect."
                  if status in (401, 403) else f"Mail fetch failed: {exc}")
        logger.warning(f"[MsgraphMailSync] {user.UserID}: {reason}")
        record_mail_access(db, user.UserID, False, reason)
        return {"linked": 0, "synced": False, "error": reason}

    for message in inbox:
        sender = (message.get("from") or {}).get("emailAddress", {}).get("address")
        result = _link_one(
            db, user, other_party_email=sender, direction="RECEIVED",
            subject=message.get("subject"),
            timestamp=_parse_graph_datetime(message.get("receivedDateTime")),
            web_link=message.get("webLink"), body=message.get("bodyPreview"),
        )
        if result:
            linked_count += 1
            if result["entity_type"] == "candidate":
                inbound_linked.append({"candidate_id": result["entity_id"], "tenant_id": user.tenant_id})

    for message in sent:
        for recipient in message.get("toRecipients") or []:
            address = (recipient.get("emailAddress") or {}).get("address")
            if _link_one(
                db, user, other_party_email=address, direction="SENT",
                subject=message.get("subject"),
                timestamp=_parse_graph_datetime(message.get("sentDateTime")),
                web_link=message.get("webLink"),
            ):
                linked_count += 1

    user.msgraph_mail_last_synced_at = now
    db.add(user)
    db.commit()
    record_mail_access(db, user.UserID, True, None)
    return {"linked": linked_count, "synced": True, "inbound_linked": inbound_linked}


def sync_user_by_id(user_id: str) -> dict:
    """Sync one user's mailbox in its own session (used right after they connect)."""
    from app.core.database import SessionLocal
    from app.core.msgraph_session_store import get_access_token

    db = SessionLocal()
    try:
        user = db.query(Users).filter(Users.UserID == user_id).first()
        token = get_access_token(user_id, db)
        if not user or not token:
            return {"linked": 0, "synced": False}
        return sync_mail_for_user(db, user, token)
    finally:
        db.close()


def run_msgraph_mail_sync_job(db: Session) -> dict:
    """Runs every few minutes (app.workers.mail_sync_worker via cron):
    syncs every user with an active Outlook connection. Per-user
    failures are isolated so one expired token can't block the rest."""
    from app.core.msgraph_session_store import active_user_ids, get_access_token

    synced_users = 0
    total_linked = 0
    failures = 0
    inbound_emails_linked = []
    for user_id in active_user_ids(db):
        user = db.query(Users).filter(Users.UserID == user_id).first()
        token = get_access_token(user_id, db) if user else None
        if not token:
            failures += 1
            continue
        result = sync_mail_for_user(db, user, token)
        if result["synced"]:
            synced_users += 1
            total_linked += result["linked"]
            inbound_emails_linked.extend(result.get("inbound_linked") or [])
        else:
            failures += 1

    if inbound_emails_linked:
        try:
            from app.services.email_reply_analysis_service import trigger_realtime_slm_update
            for item in inbound_emails_linked:
                trigger_realtime_slm_update(db, item["tenant_id"], item["candidate_id"])
        except Exception as exc:
            logger.warning(f"[MsgraphMailSync] Real-time SLM update failed (non-blocking): {exc}")

    return {"synced_users": synced_users, "failed_users": failures, "total_linked": total_linked}
