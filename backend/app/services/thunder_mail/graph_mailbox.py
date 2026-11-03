"""Microsoft Graph client for a mailbox: the shared HRMS mailbox (app-only token), or a person's own
Outlook they connected (delegated token, delegated=True; app.services.mail_sender picks which).
An email drafted in a person's mailbox copies `cc` (the helpdesk mailbox: the repository).

Needs application permissions Mail.ReadWrite + Mail.Send, scoped to the
mailbox (reading the inbox and attachments of forwarded emails needs the read half). Drafts are created then sent (instead of /sendMail, which returns no
id) so every outbound message has a conversationId to match replies against.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

from app.core.graph_auth import GraphServiceAuth
from app.services.delivery_errors import DeliveryDeferred

logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
HTTP_TIMEOUT = 20
INBOX_PAGE_SIZE = 50
INBOX_SELECT = (
    "id,conversationId,internetMessageId,from,toRecipients,ccRecipients,subject,uniqueBody,receivedDateTime,"
    "internetMessageHeaders,hasAttachments"
)
MESSAGE_SELECT = "id,subject,body,from,receivedDateTime,hasAttachments"
TEXT_BODY = 'IdType="ImmutableId", outlook.body-content-type="text"'


class GraphTransientError(RuntimeError):
    """429 / 5xx: retry later."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class GraphMailbox:
    def __init__(self, mailbox: str, http=None, token_provider=None, cc: Optional[List[str]] = None,
                 delegated: bool = False):
        self.mailbox = mailbox
        self.http = http or requests
        self.token_provider = token_provider or GraphServiceAuth.get_access_token
        self.cc = [a for a in (cc or []) if a and a.lower() != mailbox.lower()]
        self.delegated = delegated

    def _cc_recipients(self, existing: Optional[List[Dict]] = None) -> List[Dict]:
        have = {((r.get("emailAddress") or {}).get("address") or "").lower() for r in existing or []}
        return list(existing or []) + [{"emailAddress": {"address": a}} for a in self.cc if a.lower() not in have]

    def _headers(self, extra: Optional[Dict] = None) -> Dict:
        if not GraphServiceAuth.is_configured() and self.token_provider is GraphServiceAuth.get_access_token:
            raise DeliveryDeferred("Azure Graph credentials not configured")
        return {
            "Authorization": f"Bearer {self.token_provider()}",
            "Content-Type": "application/json",
            "Prefer": 'IdType="ImmutableId"',
            **(extra or {}),
        }

    def _call(self, method: str, path: str, *, json=None, params=None, headers=None, url=None):
        response = self.http.request(
            method, url or f"{GRAPH}/users/{self.mailbox}{path}",
            json=json, params=params, headers=self._headers(headers), timeout=HTTP_TIMEOUT,
        )
        if response.status_code in (401, 403) and self.delegated:
            raise DeliveryDeferred(
                f"Graph denied {method} on {self.mailbox}'s own mailbox (HTTP {response.status_code}); "
                "they must reconnect Outlook (Mail.Send + Mail.ReadWrite consent)"
            )
        if response.status_code in (401, 403):
            raise DeliveryDeferred(
                f"Graph denied {method} {path or 'nextLink'} on {self.mailbox} (HTTP {response.status_code}); "
                f"grant Mail.ReadWrite + Mail.Send application permissions for this mailbox"
            )
        if response.status_code == 429 or response.status_code >= 500:
            retry_after = response.headers.get("Retry-After")
            raise GraphTransientError(
                f"Graph {method} {path} returned {response.status_code}",
                int(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Graph {method} {path} returned {response.status_code}: {response.text[:300]}")
        return response.json() if response.content else {}

    @staticmethod
    def _ids(data: Dict) -> Tuple[str, Optional[str], Optional[str]]:
        return data["id"], data.get("conversationId"), data.get("internetMessageId")

    def create_draft(self, to: str, subject: str, html: str, ref: str) -> Tuple[str, Optional[str], Optional[str]]:
        message = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [{"emailAddress": {"address": to}}],
            "internetMessageHeaders": [{"name": "X-Thunder-Ref", "value": ref}],
        }
        if self.cc:
            message["ccRecipients"] = self._cc_recipients()
        return self._ids(self._call("POST", "/messages", json=message))

    def create_reply_draft(self, message_id: str, html: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Reply in the same thread as an earlier message (ours or the candidate's)."""
        draft = self._call("POST", f"/messages/{message_id}/createReply", json={})
        patch = {"body": {"contentType": "HTML", "content": html}}
        if self.cc:
            patch["ccRecipients"] = self._cc_recipients(draft.get("ccRecipients"))
        data = self._call("PATCH", f"/messages/{draft['id']}", json=patch)
        return self._ids({**draft, **data, "id": draft["id"]})

    def send(self, message_id: str) -> None:
        self._call("POST", f"/messages/{message_id}/send")

    def is_draft(self, message_id: str) -> bool:
        return bool(self._call("GET", f"/messages/{message_id}", params={"$select": "isDraft"}).get("isDraft"))

    def list_inbox(self, since: datetime, page_cap: int = 10) -> List[Dict]:
        return self.list_folder("inbox", since, page_cap)

    def list_folder(self, folder: str, since: datetime, page_cap: int = 10) -> List[Dict]:
        """Messages of a well-known folder (inbox, sentitems) received/sent since `since`, oldest first."""
        params = {
            "$filter": f"receivedDateTime ge {since.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "$orderby": "receivedDateTime asc",
            "$select": INBOX_SELECT,
            "$top": INBOX_PAGE_SIZE,
        }
        headers = {"Prefer": TEXT_BODY}
        messages, data = [], self._call("GET", f"/mailFolders/{folder}/messages", params=params, headers=headers)
        for _ in range(page_cap):
            messages.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            if not next_link:
                break
            data = self._call("GET", "", url=next_link, headers=headers)
        return messages

    def get_message(self, message_id: str) -> Dict:
        """The whole message as text: a forward's original email is in body, not uniqueBody."""
        return self._call("GET", f"/messages/{message_id}", params={"$select": MESSAGE_SELECT},
                          headers={"Prefer": TEXT_BODY})

    def get_message_html(self, message_id: str) -> str:
        """The message body as HTML (tables kept), for emails read by their table."""
        data = self._call("GET", f"/messages/{message_id}", params={"$select": "body"},
                          headers={"Prefer": 'IdType="ImmutableId", outlook.body-content-type="html"'})
        return (data.get("body") or {}).get("content") or ""

    def list_attachments(self, message_id: str) -> List[Dict]:
        """File attachments carry contentBytes (base64). An attached email (itemAttachment,
        "forward as attachment") is expanded so its own subject, sender and body are readable."""
        attachments = self._call("GET", f"/messages/{message_id}/attachments").get("value", [])
        for attachment in attachments:
            if attachment.get("@odata.type") == "#microsoft.graph.itemAttachment":
                expanded = self._call(
                    "GET", f"/messages/{message_id}/attachments/{attachment['id']}",
                    params={"$expand": "microsoft.graph.itemattachment/item"}, headers={"Prefer": TEXT_BODY})
                attachment["item"] = expanded.get("item") or {}
        return attachments

    def get_attachment(self, message_id: str, attachment_id: str) -> Dict:
        return self._call("GET", f"/messages/{message_id}/attachments/{attachment_id}")
