
import os
from datetime import timedelta
import logging
from typing import Optional
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
import msal
import requests
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.security import create_access_token, decode_access_token
from app.models import Users
from app.core.logging import logger
from app.core.msgraph_session_store import (
    clear_session, get_access_token, get_session_row, graph_oauth_settings, store_session,
)

load_dotenv()
REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = (os.getenv("REDIRECT_RESPONSE") or "/").rstrip("/") + "/"
# Where the browser lands after connecting Outlook
LINK_DONE_PATH = "my-tasks"

router= APIRouter(prefix="/msgraph", tags=["msgraph"])


def _msal_client():
    settings = graph_oauth_settings()
    return msal.ConfidentialClientApplication(
        settings["client_id"],
        authority=settings["authority"],
        client_credential=settings["client_secret"],
    )


def _auth_url(state: str):
    settings = graph_oauth_settings()
    params = {
        "client_id": settings["client_id"],
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        # offline_access => a refresh token, so the mailbox keeps syncing after the first hour
        "scope": " ".join(settings["scopes"] + ["offline_access", "openid", "profile"]),
        "state": state,
        "prompt": "select_account",
    }
    return f"{settings['authority']}/oauth2/v2.0/authorize?{urlencode(params)}"


@router.get("/auth/signin")
def signin():
    """Public: the "Sign in with Microsoft" login button. Microsoft SSO
    login is not wired to a WROS session yet (the callback says so); a
    logged-in user connects Outlook through /link/start instead."""
    return RedirectResponse(_auth_url(state="login"))

# ============================================
# Outlook account linking (EPIC-14/S-379 + S-435 mail capture)
# ============================================
# A user who is already logged into WROS connects their own Microsoft
# mailbox. OAuth's `state` param is the only channel that survives the
# round-trip to Microsoft, so a short-lived, narrowly-scoped "link
# intent" token rides through it and identifies the WROS user on the
# way back -- the callback itself is public (Microsoft's redirect has
# no Authorization header).
LINK_STATE_TTL_MINUTES = 10

@router.get(
    "/link/start",
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def start_link(current_user: Users = Depends(get_current_internal_user)):
    """Returns the Microsoft sign-in URL for the CURRENTLY authenticated
    WROS user to connect their Outlook. The frontend calls this with its
    normal auth header, then navigates the browser to auth_url."""
    settings = graph_oauth_settings()
    if not (settings["client_id"] and settings["client_secret"] and REDIRECT_URI):
        raise HTTPException(503, "Microsoft 365 is not configured on this server")
    link_state = create_access_token(
        data={
            "sub": current_user.UserID,
            "email": current_user.UserEmail,
            "tenant_id": current_user.tenant_id,
            "role_template_id": current_user.role_template_id,
            "msgraph_link": True,
        },
        expires_delta=timedelta(minutes=LINK_STATE_TTL_MINUTES),
    )
    return {"auth_url": _auth_url(state=link_state)}

@router.get(
    "/link-status",
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def link_status(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    row = get_session_row(db, current_user.UserID)
    if row is None:
        from app.models.msgraph_session import MsgraphSession
        old = db.query(MsgraphSession).filter(MsgraphSession.user_id == current_user.UserID).first()
        return {"linked": False, "last_error": old.last_error if old else None}
    synced = current_user.msgraph_mail_last_synced_at
    return {
        "linked": True,
        "account_email": row.account_email,
        "mail_access": row.mail_access,
        "last_error": row.last_error,
        "last_synced_at": synced.isoformat() if synced else None,
    }

@router.post(
    "/unlink",
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def unlink(current_user: Users = Depends(get_current_internal_user)):
    clear_session(current_user.UserID)
    return {"linked": False}

def _decode_link_state(state: str) -> Optional[str]:
    """The WROS UserID a link-intent state token names, or None for any
    other state (the login button, garbage, expired)."""
    if not state or state == "login":
        return None
    try:
        payload = decode_access_token(state)
    except HTTPException:
        return None
    if not payload.get("msgraph_link"):
        return None
    return payload.get("sub")

def _link_redirect(status: str, reason: str = "") -> RedirectResponse:
    params = {"outlook": status}
    if reason:
        params["reason"] = reason[:200]
    return RedirectResponse(url=f"{FRONTEND_URL}{LINK_DONE_PATH}?{urlencode(params)}")

def oauth_callback(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Microsoft redirects here (GET) after sign-in. Public by necessity;
    the state token identifies the WROS user. Served both at
    /api/v1/msgraph/auth/callback and at the registered redirect URI
    path /msgraph/auth/callback (see app.main)."""
    if request.query_params.get("error"):
        return _link_redirect("error", request.query_params.get("error_description") or request.query_params.get("error"))
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(400, "Missing auth code")

    user_id = _decode_link_state(request.query_params.get("state"))
    if not user_id:
        # Login button: Microsoft SSO into WROS is not implemented.
        return RedirectResponse(url=f"{FRONTEND_URL}?{urlencode({'sso': 'unavailable'})}")
    user = db.query(Users).filter(Users.UserID == user_id).first()
    if not user:
        return _link_redirect("error", "WROS user not found; sign in again and retry")

    settings = graph_oauth_settings()
    token_result = _msal_client().acquire_token_by_authorization_code(
        code, scopes=settings["scopes"], redirect_uri=REDIRECT_URI,
    )
    if "access_token" not in token_result:
        logger.warning(f"[msgraph] Token exchange failed for {user.UserEmail}: {token_result.get('error_description')}")
        return _link_redirect("error", token_result.get("error_description") or "Microsoft sign-in failed")

    claims = token_result.get("id_token_claims") or {}
    account_id = claims.get("oid")
    if not account_id:
        return _link_redirect("error", "Microsoft did not return an account id")
    store_session(user.UserID, account_id, token_result,
                  account_email=claims.get("preferred_username") or claims.get("email"))

    # First sync right away (last 24h), so the user sees results without waiting for the timer
    from app.services.msgraph_mail_sync_service import sync_user_by_id
    background_tasks.add_task(sync_user_by_id, user.UserID)
    return _link_redirect("connected")

router.add_api_route("/auth/callback", oauth_callback, methods=["GET"], include_in_schema=False)

def _graph_client_for(user_id: str) -> dict:
    """Access token for Graph calls on behalf of this WROS user."""
    token = get_access_token(user_id)
    if not token:
        raise HTTPException(401, "Outlook is not connected or the session expired. Connect Outlook from My Tasks.")
    return {"access_token": token}

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
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def me(db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    """The current WROS user plus whether their Outlook is connected."""
    row = get_session_row(db, user.UserID)
    return JSONResponse({
        "user": {
            "id": user.UserID,
            "name": user.UserName,
            "email": user.UserEmail,
            "type": user.UserRole,
            "outlook_connected": row is not None,
        }
    })

def _require_account(current_user: Users = Depends(get_current_internal_user)) -> str:
    """The calling user's own id (from their JWT, never a client value),
    after checking their Outlook is connected. Callers pass it to
    _graph_client_for()."""
    if get_access_token(current_user.UserID) is None:
        raise HTTPException(401, "Outlook is not connected or the session expired. Connect Outlook from My Tasks.")
    return current_user.UserID

# ---------- SEND MAIL ----------
@router.post(
    "/mail/send",
    dependencies=[Depends(require_resource_permission("configuration", "create"))]
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
    dependencies=[Depends(require_resource_permission("configuration", "create"))]
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
    dependencies=[Depends(require_resource_permission("configuration", "view"))]
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
    dependencies=[Depends(require_resource_permission("configuration", "view"))],
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
    dependencies=[Depends(require_resource_permission("configuration", "edit"))],
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
    dependencies=[Depends(require_resource_permission("configuration", "edit"))],
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
        logger.error(f"SharePoint test connection error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": "SharePoint connection test failed",
            "details": str(e),
            "configured": False
        }

@router.get(
    "/sharepoint/list-drives",
    dependencies=[Depends(require_resource_permission("configuration", "edit"))],
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
