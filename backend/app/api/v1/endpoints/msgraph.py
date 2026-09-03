
import os
from datetime import timedelta
import logging
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
import msal
import requests
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.security import create_access_token, decode_access_token
from app.models import Users,Role
from app.core.logging import logger
from app.core.msgraph_session_store import (
    account_id_by_user_id as _account_id_by_user_id,
    user_tokens,
)






load_dotenv()
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = os.getenv("AUTHORITY") or f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPES = (os.getenv("SCOPES") or "https://graph.microsoft.com/.default").split()

redirect_url = os.getenv("REDIRECT_RESPONSE")

router= APIRouter(prefix="/msgraph", tags=["msgraph"])

# user_tokens / _account_id_by_user_id now live in
# app.core.msgraph_session_store (EPIC-14/S-435 needs the mail-sync
# service to read the same live state without importing from this
# endpoints module) -- imported above, not redefined here.

def _msal_client():
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )

def _auth_url(state: str = "xyz"):
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": " ".join(SCOPES),
        "state": state,
        # optionally include PKCE values here if you implement code_verifier/challenge
    }
    return f"{AUTHORITY}/oauth2/v2.0/authorize?{urlencode(params)}"

@router.get(
    "/auth/signin",
    dependencies=[Depends(require_resource_permission("auth", "view"))]
)
def signin():
    return RedirectResponse(_auth_url())


# ============================================
# EPIC-14/S-379 (HRMS-1401) -- M365 Launchpad account linking
# ============================================
# 2026-08-05: the flow above (/auth/signin -> /auth/callback) was built
# for one purpose only -- get a Graph token to send mail/schedule a
# meeting on behalf of whoever completes it, minting a *fresh* WROS
# session in the process. The Launchpad needs a second, different use
# case: a user who is ALREADY logged into WROS wants to link their
# Microsoft account so the Launchpad can show their real mail/calendar/
# chat -- linking must NOT silently swap out their current WROS
# session token as a side effect. OAuth's own `state` param is the only
# channel that survives the round-trip to Microsoft and back, so a
# short-lived, narrowly-scoped "link intent" token (same
# Depends()-checked-claim pattern as MFA's mfa_pending token, see
# app.core.dependencies.get_current_mfa_pending_user) rides through it.
# /auth/callback below checks for this claim FIRST and, if present,
# takes the link-only path -- every other `state` value (including the
# old hardcoded "xyz" default) falls through to the ORIGINAL,
# byte-for-byte-unchanged login behavior.
LINK_STATE_TTL_MINUTES = 10


@router.get(
    "/link/start",
    dependencies=[Depends(require_resource_permission("link", "view"))]
)
def start_link(current_user: Users = Depends(get_current_internal_user)):
    """Returns the Microsoft sign-in URL for the CURRENTLY authenticated
    WROS user to link their M365 account. The frontend must call this
    via an authenticated fetch (not a plain <a href>, since a real
    browser navigation carries no Authorization header) and then
    navigate the browser to the returned auth_url itself."""
    link_state = create_access_token(
        data={"sub": current_user.UserEmail, "msgraph_link": True},
        expires_delta=timedelta(minutes=LINK_STATE_TTL_MINUTES),
    )
    return {"auth_url": _auth_url(state=link_state)}


@router.get(
    "/link-status",
    dependencies=[Depends(require_resource_permission("link-statu", "view"))]
)
def link_status(current_user: Users = Depends(get_current_internal_user)):
    account_id = _account_id_by_user_id.get(current_user.UserID)
    linked = bool(account_id and account_id in user_tokens)
    return {"linked": linked}


@router.post(
    "/unlink",
    dependencies=[Depends(require_resource_permission("unlink", "create"))]
)
def unlink(current_user: Users = Depends(get_current_internal_user)):
    account_id = _account_id_by_user_id.pop(current_user.UserID, None)
    if account_id:
        user_tokens.pop(account_id, None)
    return {"linked": False}


def _decode_link_state(state: str):
    """Returns the Users row this state token names, or None if `state`
    isn't a valid, unexpired link-intent token -- i.e. every non-link
    caller of /auth/callback (the original login flow, or garbage/
    missing state) gets None here and falls through unaffected."""
    if not state:
        return None
    try:
        payload = decode_access_token(state)
    except HTTPException:
        raise ValueError("Operation failed")
    if not payload.get("msgraph_link"):
        raise ValueError("Operation failed")
    return payload.get("sub")


@router.get(
    "/auth/callback",
    dependencies=[Depends(require_resource_permission("auth", "view"))]
)
def callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(400, "Missing auth code")

    app_msal = _msal_client()
    token_result = app_msal.acquire_token_by_authorization_code(
        code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    if "access_token" not in token_result:
        raise HTTPException(401, f"Token error: {token_result.get('error_description')}")

    # Persist token in-memory (used by Graph API endpoints like /mail/send)
    account_id = token_result.get("id_token_claims", {}).get("oid")
    if not account_id:
        raise HTTPException(401, "Could not determine user identity (missing oid claim)")
    user_tokens[account_id] = token_result

    # ---- Account-linking path (S-379): an already-logged-in WROS user
    # asked to link their M365 account -- link it to THEIR real row and
    # bounce back to the Launchpad without touching their WROS session.
    link_target_email = _decode_link_state(request.query_params.get("state"))
    if link_target_email:
        linked_user = db.query(Users).filter(Users.UserEmail == link_target_email).first()
        if linked_user:
            _account_id_by_user_id[linked_user.UserID] = account_id
            return RedirectResponse(url=f"{redirect_url}m365?linked=true")
        # Falls through to the original flow below if the linking
        # user's row somehow no longer exists -- fail open to "just
        # log this Microsoft identity in normally" rather than a dead end.

    # ---- Original flow (unchanged): mint a fresh WROS session for
    # whoever just signed into Microsoft, creating a Users row if this
    # is their first time.
    graph_resp = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {token_result['access_token']}"},
        timeout=10,
    )
    graph_resp.raise_for_status()
    graph_user = graph_resp.json()

    email = graph_user.get("mail") or graph_user.get("userPrincipalName")
    display_name = graph_user.get("displayName", "")
    ms_user_id = graph_user.get("id")

    # Look up or auto-create user in DB
    user = db.query(Users).filter(Users.UserEmail == email).first()
    if not user:
        user = Users(
            UserID=ms_user_id,
            UserName=display_name,
            UserEmail=email,
            UserRole="employee",
            UserPassword="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 2026-08-05 real bug fix -- see _require_account()'s own docstring.
    _account_id_by_user_id[user.UserID] = account_id

    role = db.query(Role).filter(Role.id == user.role_id).first() if user.role_id else None

    # Create JWT â€” this is all the client needs going forward
    jwt_token = create_access_token(
        data={
            "sub": user.UserEmail,
            "type": user.UserRole,
            "name": user.UserName,
        }
    )

    # Redirect to frontend with the JWT as a query param
    # The frontend should store this token and send it as `Authorization: Bearer <token>`
    params = urlencode({"token": jwt_token})
    return RedirectResponse(url=f"{redirect_url}?{params}")

def _graph_client_for(account_id: str) -> dict:
    """
    Return the access token for making Graph API calls.
    We'll use requests library for simplicity instead of the complex SDK setup.
    """
    if account_id not in user_tokens:
        raise HTTPException(401, "No token found for user")
    return user_tokens[account_id]

def _make_graph_request(method: str, endpoint: str, access_token: str, json_data=None):
    """
    Helper to make Graph API requests using requests library.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"https://graph.microsoft.com/v1.0{endpoint}"
    
    if method.upper() == "GET":
        response = requests.get(url, headers=headers)
    elif method.upper() == "POST":
        response = requests.post(url, headers=headers, json=json_data)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # Try to get error details from response
        error_detail = "Unknown error"
        try:
            error_json = response.json()
            error_detail = error_json.get("error", {}).get("message", str(e))
        except:
            error_detail = f"{e.response.status_code} {e.response.reason}"
        
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Microsoft Graph API error: {error_detail}"
        )
    
    return response

@router.get(
    "/me",
    dependencies=[Depends(require_resource_permission("me", "view"))]
)
def me(db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    """
    Return the current authenticated user's profile from the database.
    Requires a valid JWT Bearer token (obtained from /auth/callback redirect).

    Returns:
        User details
    """
    role = db.query(Role).filter(Role.id == user.role_id).first() if user.role_id else None

    return JSONResponse({
        "user": {
            "id": user.UserID,
            "name": user.UserName,
            "email": user.UserEmail,
            "type": user.UserRole,
            "permission_role": role.name if role else None,
        }
    })

def _require_account(current_user: Users = Depends(get_current_internal_user)) -> str:
    """
    Identify the calling user's linked Microsoft account from their real
    authenticated session (the same JWT every other endpoint in this
    app uses), never a client-suppliable value.

    Real bug fix, 2026-08-05: this used to read `request.cookies.get(
    "account_id")` -- a cookie /auth/callback never actually sets
    anywhere (confirmed by grep: no set_cookie call exists in this
    file), so every call through this path always 401'd in real usage,
    silently breaking "Schedule Interview"'s Microsoft Teams meeting
    creation. Worse than just broken: even if a future edit started
    setting that cookie, trusting a raw, unsigned cookie value as a
    direct key into `user_tokens` (which holds real Graph access
    tokens -- mail send, calendar read/write) with no cross-check
    against the actual authenticated caller would be a real IDOR --
    anyone who learned/guessed another user's MS `oid` could set it
    client-side and use that user's Graph token. Fixed the same way
    every other "resolve MY OWN data" endpoint in this codebase
    already does: derive identity from Depends(get_current_internal_user)
    (the real JWT), never a request-supplied identifier.
    """
    account_id = _account_id_by_user_id.get(current_user.UserID)
    if not account_id or account_id not in user_tokens:
        raise HTTPException(401, "Microsoft account not linked or session expired. Please sign in again at /msgraph/auth/signin")
    return account_id

# ---------- SEND MAIL ----------
@router.post(
    "/mail/send",
    dependencies=[Depends(require_resource_permission("mail", "create"))]
)
def send_mail(to: str, subject: str, body_text: str, account_id: str = Depends(_require_account)):
    token_data = _graph_client_for(account_id)

    # Build the message payload as JSON
    message_payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body_text
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to
                    }
                }
            ]
        }
    }

    _make_graph_request("POST", "/me/sendMail", token_data["access_token"], message_payload)
    return {"status": "Mail sent"}

# ---------- CREATE MEETING (CALENDAR EVENT) ----------
@router.post(
    "/calendar/schedule",
    dependencies=[Depends(require_resource_permission("calendar", "create"))]
)
def schedule_meeting(
    subject: str,
    start_iso: str,
    end_iso: str,
    timezone: str = "India Standard Time",
    attendees: list[str] = [],
    teams_online: bool = True,
    account_id: str = Depends(_require_account),
):
    token_data = _graph_client_for(account_id)

    # Build the event payload as JSON
    event_payload = {
        "subject": subject,
        "start": {
            "dateTime": start_iso,
            "timeZone": timezone
        },
        "end": {
            "dateTime": end_iso,
            "timeZone": timezone
        },
        "attendees": [
            {
                "emailAddress": {"address": a},
                "type": "required"
            } for a in attendees
        ]
    }

    if teams_online:
        event_payload["isOnlineMeeting"] = True
        event_payload["onlineMeetingProvider"] = "teamsForBusiness"

    resp = _make_graph_request("POST", "/me/events", token_data["access_token"], event_payload)
    created_json = resp.json()

    # If online meeting, Graph returns onlineMeeting.joinUrl inside event
    join_url = (created_json.get("onlineMeeting") or {}).get("joinUrl")
    return {"eventId": created_json.get("id"), "joinUrl": join_url}


@router.get(
    "/calendar/meetings",
    dependencies=[Depends(require_resource_permission("calendar", "view"))]
)
def get_my_meetings(
    top: int = 10,
    skip: int = 0,
    account_id: str = Depends(_require_account),
):
    '''
    Get user's calendar meetings/events.

    Args:
        top: Number of events to return (default: 10, max: 100)
        skip: Number of events to skip for pagination (default: 0)

    Returns:
        List of calendar events with details
    '''
    token_data = _graph_client_for(account_id)
    
    # Validate parameters
    if top > 100:
        top = 100
    if top < 1:
        top = 10
    if skip < 0:
        skip = 0
    
    # Get calendar events with pagination
    endpoint = f"/me/events?$top={top}&$skip={skip}&$orderby=start/dateTime"
    resp = _make_graph_request("GET", endpoint, token_data["access_token"])
    events_data = resp.json()
    
    # Format events for response
    events = []
    for event in events_data.get("value", []):
        event_info = {
            "id": event.get("id"),
            "subject": event.get("subject"),
            "start": event.get("start", {}).get("dateTime"),
            "end": event.get("end", {}).get("dateTime"),
            "timeZone": event.get("start", {}).get("timeZone"),
            "location": event.get("location", {}).get("displayName"),
            "isOnlineMeeting": event.get("isOnlineMeeting", False),
            "onlineMeetingUrl": event.get("onlineMeeting", {}).get("joinUrl") if event.get("onlineMeeting") else None,
            "organizer": event.get("organizer", {}).get("emailAddress", {}).get("name"),
            "attendees": [
                {
                    "name": attendee.get("emailAddress", {}).get("name"),
                    "email": attendee.get("emailAddress", {}).get("address"),
                    "status": attendee.get("status", {}).get("response")
                }
                for attendee in event.get("attendees", [])
            ],
            "webLink": event.get("webLink"),
            "createdDateTime": event.get("createdDateTime"),
            "lastModifiedDateTime": event.get("lastModifiedDateTime")
        }
        events.append(event_info)
    
    return {
        "status": "success",
        "count": len(events),
        "total": events_data.get("@odata.count"),
        "events": events,
        "pagination": {
            "top": top,
            "skip": skip,
            "hasMore": len(events) == top
        }
    }


# ============================================
# Service Account Calendar Endpoints
# Uses Application-level permissions (no user sign-in required)
# ============================================

from app.core.graph_auth import get_graph_token, GraphServiceAuth


@router.get(
    "/service/calendar/events/{user_email}",
    dependencies=[Depends(require_resource_permission("calendar", "view"))],
)
def get_user_calendar_events(
    user_email: str,
    start_time: str = None,
    end_time: str = None,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db)
):
    '''
    Get calendar events for a specific user within a date range using service account.
    Uses Application-level permissions (Calendars.ReadWrite).
    No user sign-in required.
    
    Args:
        user_email: Email address of the user whose calendar to read
        start_time: Start of date range in ISO format (e.g., "2026-02-03T00:00:00")
                   If not provided, defaults to current date at 00:00:00
        end_time: End of date range in ISO format (e.g., "2026-02-10T23:59:59")
                 If not provided, defaults to 7 days from start_time
    
    Returns:
        List of calendar events for the specified user within the date range
    '''
    try:
        # Audit log: Track who is accessing calendars
        logger.info(
            f"CALENDAR ACCESS | HR User: {current_user.UserEmail} (ID: {current_user.UserID}) | "
            f"Target: {user_email} | Date Range: {start_time or 'default'} to {end_time or 'default'} | "
            f"Action: Read Calendar Events"
        )
        
        from datetime import datetime, timedelta
        
        # Get service account token
        access_token = get_graph_token()
        
        # Set default date range if not provided
        if not start_time:
            # Default to today at 00:00:00
            start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_time = start_dt.isoformat()
        else:
            start_dt = datetime.fromisoformat(start_time.replace('Z', ''))
        
        if not end_time:
            # Default to 7 days from start_time
            end_dt = start_dt + timedelta(days=7)
            end_time = end_dt.isoformat()
        
        # Build filter query for date range
        # Microsoft Graph uses $filter with start/dateTime and end/dateTime
        filter_query = f"start/dateTime ge '{start_time}' and end/dateTime le '{end_time}'"
        
        # Get calendar events for specific user with date filter
        headers = {"Authorization": f"Bearer {access_token}"}
        endpoint = f"https://graph.microsoft.com/v1.0/users/{user_email}/calendarView?startDateTime={start_time}&endDateTime={end_time}&$orderby=start/dateTime"
        
        response = requests.get(endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        events_data = response.json()
        
        # Format events for response
        events = []
        for event in events_data.get("value", []):
            event_info = {
                "id": event.get("id"),
                "subject": event.get("subject"),
                "start": event.get("start", {}).get("dateTime"),
                "end": event.get("end", {}).get("dateTime"),
                "timeZone": event.get("start", {}).get("timeZone"),
                "location": event.get("location", {}).get("displayName"),
                "isOnlineMeeting": event.get("isOnlineMeeting", False),
                "onlineMeetingUrl": event.get("onlineMeeting", {}).get("joinUrl") if event.get("onlineMeeting") else None,
                "organizer": event.get("organizer", {}).get("emailAddress", {}).get("name"),
                "organizerEmail": event.get("organizer", {}).get("emailAddress", {}).get("address"),
                "attendees": [
                    {
                        "name": attendee.get("emailAddress", {}).get("name"),
                        "email": attendee.get("emailAddress", {}).get("address"),
                        "status": attendee.get("status", {}).get("response")
                    }
                    for attendee in event.get("attendees", [])
                ],
                "webLink": event.get("webLink"),
                "createdDateTime": event.get("createdDateTime"),
                "lastModifiedDateTime": event.get("lastModifiedDateTime")
            }
            events.append(event_info)
        
        # Log successful retrieval
        logger.info(
            f"CALENDAR ACCESS SUCCESS | HR User: {current_user.UserEmail} | "
            f"Target: {user_email} | Retrieved: {len(events)} events"
        )
        
        return {
            "status": "success",
            "user": user_email,
            "count": len(events),
            "start_time": start_time,
            "end_time": end_time,
            "events": events
        }
        
    except requests.exceptions.HTTPError as e:
        error_detail = "Unknown error"
        try:
            error_json = e.response.json()
            error_detail = error_json.get("error", {}).get("message", str(e))
        except:
            error_detail = f"{e.response.status_code} {e.response.reason}"
        
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Microsoft Graph API error: {error_detail}"
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch calendar events: {str(e)}")


@router.post(
    "/service/calendar/schedule",
    dependencies=[Depends(require_resource_permission("calendar", "edit"))],
)
def schedule_meeting_for_user(
    organizer_email: str,
    subject: str,
    start_iso: str,
    end_iso: str,
    attendees: list[str] = [],
    timezone: str = "UTC",
    teams_online: bool = True,
    location: str = None,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db)
):
    '''
    Schedule a meeting for a specific user using service account.
    Uses Application-level permissions (Calendars.ReadWrite, OnlineMeetings.ReadWrite.All).
    No user sign-in required.
    
    Args:
        organizer_email: Email of the user who will be the organizer
        subject: Meeting subject/title
        start_iso: Start time in ISO format (e.g., "2026-02-03T10:00:00")
        end_iso: End time in ISO format
        attendees: List of attendee email addresses
        timezone: Timezone (default: UTC)
        teams_online: Create as Teams online meeting (default: True)
        location: Physical location (optional)
    
    Returns:
        Event ID and Teams join URL (if online meeting)
    '''
    # Audit log: Track who is scheduling meetings
    logger.info(
        f"MEETING SCHEDULE | HR User: {current_user.UserEmail} (ID: {current_user.UserID}) | "
        f"Organizer: {organizer_email} | Subject: '{subject}' | "
        f"Time: {start_iso} to {end_iso} | Attendees: {len(attendees)} | Teams: {teams_online}"
    )
    
    try:
        # Get service account token
        access_token = get_graph_token()
        
        # Build the event payload
        event_payload = {
            "subject": subject,
            "start": {
                "dateTime": start_iso,
                "timeZone": timezone
            },
            "end": {
                "dateTime": end_iso,
                "timeZone": timezone
            },
            "attendees": [
                {
                    "emailAddress": {"address": email},
                    "type": "required"
                } for email in attendees
            ]
        }
        
        # Add location if provided
        if location:
            event_payload["location"] = {
                "displayName": location
            }
        
        # Add Teams online meeting if requested
        if teams_online:
            event_payload["isOnlineMeeting"] = True
            event_payload["onlineMeetingProvider"] = "teamsForBusiness"
        
        # Create event in user's calendar
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        endpoint = f"https://graph.microsoft.com/v1.0/users/{organizer_email}/events"
        
        response = requests.post(endpoint, headers=headers, json=event_payload, timeout=10)
        response.raise_for_status()
        created_event = response.json()
        
        # Extract meeting details
        join_url = None
        if created_event.get("onlineMeeting"):
            join_url = created_event["onlineMeeting"].get("joinUrl")
        
        # Log successful meeting creation
        logger.info(
            f"MEETING CREATED | HR User: {current_user.UserEmail} | "
            f"Organizer: {organizer_email} | Event ID: {created_event.get('id')} | "
            f"Teams: {teams_online} | Join URL: {'Yes' if join_url else 'No'}"
        )
        
        return {
            "status": "success",
            "message": f"Meeting scheduled successfully for {organizer_email}",
            "eventId": created_event.get("id"),
            "subject": created_event.get("subject"),
            "start": created_event.get("start", {}).get("dateTime"),
            "end": created_event.get("end", {}).get("dateTime"),
            "organizer": organizer_email,
            "isOnlineMeeting": created_event.get("isOnlineMeeting", False),
            "joinUrl": join_url,
            "webLink": created_event.get("webLink")
        }
        
    except requests.exceptions.HTTPError as e:
        error_detail = "Unknown error"
        try:
            error_json = e.response.json()
            error_detail = error_json.get("error", {}).get("message", str(e))
        except:
            error_detail = f"{e.response.status_code} {e.response.reason}"
        
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Microsoft Graph API error: {error_detail}"
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to schedule meeting: {str(e)}")


# ============================================
# SharePoint Connection Test
# ============================================

@router.get(
    "/sharepoint/test-connection",
    dependencies=[Depends(require_resource_permission("roles-permissions", "edit"))],
)
def test_sharepoint_connection(
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Test SharePoint connection and list available folders.
    Uses service account authentication.
    
    Returns:
        Connection status and folder list
    """
    try:
        # Audit log: Track SharePoint access
        logger.info("SHAREPOINT ACCESS | Action: Test Connection | Service: SharePoint Drive Test")
        
        # Check if service account is configured
        if not GraphServiceAuth.is_configured():
            return {
                "status": "error",
                "message": "Service account not configured",
                "details": "Please set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET in .env file",
                "configured": False
            }
        
        # Get access token
        try:
            access_token = get_graph_token()
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": "Failed to get access token",
                "details": str(e),
                "configured": True,
                "authenticated": False
            }
        
        # Test SharePoint access
        site_id = os.getenv("SHAREPOINT_SITE_ID", "")
        drive_id = os.getenv("SHAREPOINT_DRIVE_ID", "")
        base_folder = os.getenv("SHAREPOINT_BASE_FOLDER", "CandidateDocuments")
        
        if not site_id or not drive_id:
            return {
                "status": "error",
                "message": "SharePoint not configured",
                "details": "Please set SHAREPOINT_SITE_ID and SHAREPOINT_DRIVE_ID in .env file",
                "configured": True,
                "authenticated": True,
                "sharepoint_configured": False
            }
        
        # Get site information
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            # Get site details
            site_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            site_response = requests.get(site_url, headers=headers, timeout=10)
            site_response.raise_for_status()
            site_data = site_response.json()
            
            # Get drive details
            drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}"
            drive_response = requests.get(drive_url, headers=headers, timeout=10)
            drive_response.raise_for_status()
            drive_data = drive_response.json()
            
            # List folders in base folder
            folders = []
            try:
                folder_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{base_folder}:/children"
                folder_response = requests.get(folder_url, headers=headers, timeout=10)
                
                if folder_response.status_code == 200:
                    items = folder_response.json().get("value", [])
                    folders = [
                        {
                            "name": item["name"],
                            "type": "folder" if item.get("folder") else "file",
                            "size": item.get("size", 0),
                            "created": item.get("createdDateTime"),
                            "modified": item.get("lastModifiedDateTime"),
                            "webUrl": item.get("webUrl")
                        }
                        for item in items
                    ]
                elif folder_response.status_code == 404:
                    folders = []
                    base_folder_exists = False
                else:
                    folder_response.raise_for_status()
            except Exception as folder_error:
                logger.error(f"Error: {str(folder_error)}", exc_info=True)
                logger.warning(f"Could not list folders: {str(folder_error)}")
                folders = []
            
            return {
                "status": "success",
                "message": "SharePoint connection successful",
                "configured": True,
                "authenticated": True,
                "sharepoint_configured": True,
                "connection": {
                    "site": {
                        "id": site_data.get("id"),
                        "name": site_data.get("displayName"),
                        "webUrl": site_data.get("webUrl")
                    },
                    "drive": {
                        "id": drive_data.get("id"),
                        "name": drive_data.get("name"),
                        "driveType": drive_data.get("driveType"),
                        "webUrl": drive_data.get("webUrl")
                    },
                    "baseFolder": base_folder,
                    "folderCount": len(folders),
                    "folders": folders
                }
            }
            
        except requests.exceptions.HTTPError as e:
            return {
                "status": "error",
                "message": "SharePoint access denied",
                "details": f"HTTP {e.response.status_code}: {e.response.text}",
                "configured": True,
                "authenticated": True,
                "sharepoint_configured": True,
                "access_granted": False
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": "Failed to access SharePoint",
                "details": str(e),
                "configured": True,
                "authenticated": True,
                "sharepoint_configured": True
            }
            
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"SharePoint connection test failed: {str(e)}")
        return {
            "status": "error",
            "message": "Connection test failed",
            "details": str(e)
        }



@router.get(
    "/sharepoint/list-drives",
    dependencies=[Depends(require_resource_permission("roles-permissions", "edit"))],
)
def list_sharepoint_drives(
    current_user: Users = Depends(get_current_internal_user)
):
    '''
    List all drives available in the SharePoint site.
    Helps identify the correct Drive ID to use in .env file.
    
    Returns:
        List of drives with their IDs and names
    '''
    try:
        # Audit log: Track SharePoint drive listing
        logger.info("SHAREPOINT ACCESS | Action: List Drives | Service: SharePoint Site Drives")
        
        # Check if service account is configured
        if not GraphServiceAuth.is_configured():
            return {
                "status": "error",
                "message": "Service account not configured",
                "details": "Please set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET in .env file"
            }
        
        # Get access token
        try:
            access_token = get_graph_token()
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": "Failed to get access token",
                "details": str(e)
            }
        
        # Get site ID
        site_id = os.getenv("SHAREPOINT_SITE_ID", "")
        if not site_id:
            return {
                "status": "error",
                "message": "SHAREPOINT_SITE_ID not configured",
                "details": "Please set SHAREPOINT_SITE_ID in .env file"
            }
        
        # List all drives for the site
        headers = {"Authorization": f"Bearer {access_token}"}
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        
        response = requests.get(drives_url, headers=headers, timeout=10)
        response.raise_for_status()
        drives_data = response.json()
        
        drives = []
        for drive in drives_data.get("value", []):
            drives.append({
                "id": drive.get("id"),
                "name": drive.get("name"),
                "driveType": drive.get("driveType"),
                "webUrl": drive.get("webUrl"),
                "description": drive.get("description", "N/A")
            })
        
        return {
            "status": "success",
            "message": f"Found {len(drives)} drive(s)",
            "drives": drives,
            "instructions": "Copy the 'id' of the drive you want to use and set it as SHAREPOINT_DRIVE_ID in your .env file"
        }
        
    except requests.exceptions.HTTPError as e:
        error_detail = "Unknown error"
        try:
            error_json = e.response.json()
            error_detail = error_json.get("error", {}).get("message", str(e))
        except:
            error_detail = f"{e.response.status_code} {e.response.reason}"
        
        return {
            "status": "error",
            "message": "Failed to list drives",
            "details": error_detail
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": "Failed to list drives",
            "details": str(e)
        }
