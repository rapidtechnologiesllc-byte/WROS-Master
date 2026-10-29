"""Microsoft Graph calls for performance reviews: book the Teams meeting (recorded automatically) and
fetch its recording afterwards. The organizer is the service mailbox, as for interview invites.

Permissions the Graph app needs (granted by an Azure / Teams admin):
- booking: Calendars.ReadWrite, OnlineMeetings.ReadWrite.All
- recordings: OnlineMeetingRecording.Read.All, plus a Teams application access policy that lets the
  app act for the service mailbox (New-CsApplicationAccessPolicy / Grant-CsApplicationAccessPolicy)

Every failure raises GraphError with Microsoft's message, so the caller records why on the review.
"""
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import quote

import requests

from app.services.email_service import EmailService

GRAPH = "https://graph.microsoft.com/v1.0"
TIMEOUT_SECONDS = 30


class GraphError(RuntimeError):
    pass


def _headers() -> dict:
    return {"Authorization": f"Bearer {EmailService._get_token()}", "Content-Type": "application/json"}


def _check(response: requests.Response, what: str) -> requests.Response:
    if response.status_code >= 400:
        try:
            message = response.json().get("error", {}).get("message", response.text[:300])
        except ValueError:
            message = response.text[:300]
        raise GraphError(f"{what}: HTTP {response.status_code} {message}")
    return response


def _organizer() -> str:
    return quote(EmailService.SERVICE_EMAIL)


def book_meeting(*, subject: str, body_html: str, start: datetime, end: datetime, timezone: str,
                 attendee_emails: list) -> Tuple[str, Optional[str]]:
    """Create the Teams calendar event on every attendee's calendar. Returns (event id, join url)."""
    payload = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body_html},
        "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": timezone},
        "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": timezone},
        "attendees": [{"emailAddress": {"address": e}, "type": "required"} for e in attendee_emails],
        "isOnlineMeeting": True,
        "onlineMeetingProvider": "teamsForBusiness",
    }
    response = _check(requests.post(f"{GRAPH}/users/{_organizer()}/events", headers=_headers(), json=payload,
                                    timeout=TIMEOUT_SECONDS), "Booking the Teams meeting")
    event = response.json()
    return event["id"], (event.get("onlineMeeting") or {}).get("joinUrl")


def _online_meeting_id(join_url: str) -> str:
    response = _check(requests.get(f"{GRAPH}/users/{_organizer()}/onlineMeetings", headers=_headers(),
                                   params={"$filter": f"JoinWebUrl eq '{join_url}'"}, timeout=TIMEOUT_SECONDS),
                      "Finding the Teams meeting")
    meetings = response.json().get("value") or []
    if not meetings:
        raise GraphError("Finding the Teams meeting: no meeting has this join link")
    return meetings[0]["id"]


def record_automatically(join_url: str) -> None:
    """Turn on automatic recording, so the session is recorded without anyone pressing Record."""
    meeting_id = _online_meeting_id(join_url)
    _check(requests.patch(f"{GRAPH}/users/{_organizer()}/onlineMeetings/{meeting_id}", headers=_headers(),
                          json={"recordAutomatically": True}, timeout=TIMEOUT_SECONDS),
           "Turning on automatic recording")


def fetch_recording(join_url: str, max_bytes: int) -> Optional[bytes]:
    """The meeting's first recording, or None when Teams has none yet (still processing, or the
    meeting did not happen)."""
    meeting_id = _online_meeting_id(join_url)
    base = f"{GRAPH}/users/{_organizer()}/onlineMeetings/{meeting_id}/recordings"
    recordings = _check(requests.get(base, headers=_headers(), timeout=TIMEOUT_SECONDS),
                        "Listing the meeting recordings").json().get("value") or []
    if not recordings:
        return None
    content = _check(requests.get(f"{base}/{recordings[0]['id']}/content", headers=_headers(),
                                  timeout=TIMEOUT_SECONDS * 10, stream=True), "Downloading the recording")
    data = bytearray()
    for chunk in content.iter_content(chunk_size=1024 * 1024):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise GraphError(f"The recording is larger than {max_bytes // (1024 * 1024)} MB")
    return bytes(data)
