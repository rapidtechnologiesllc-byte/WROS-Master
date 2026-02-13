
import os
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
import msal
import requests
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.core.security import create_access_token
from app.models import Users
from app.core.logging import logger







load_dotenv()
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = os.getenv("AUTHORITY") or f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPES = os.getenv("SCOPES").split()

redirect_url = os.getenv("REDIRECT_RESPONSE")

router= APIRouter(prefix="/msgraph", tags=["msgraph"])

# Simple in-memory "session" for demo (swap with Redis/DB in production)
user_tokens = {}

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

@router.get("/auth/signin")
def signin():
    return RedirectResponse(_auth_url())

@router.get("/auth/callback")
def callback(request: Request):
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

    # Use user’s oid (object id) as key; UPN works too
    account_id = token_result.get("id_token_claims", {}).get("oid")
    user_tokens[account_id] = token_result  # store access & refresh token for later

    return RedirectResponse(url=redirect_url)

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

@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    """
    Get user profile from Microsoft Graph and auto-register in database.
    
    Returns:
        User details with JWT access token
    """
    account_id = _require_account(request)
    token_data = _graph_client_for(account_id)
    
    # Get user info from Microsoft Graph
    resp = _make_graph_request("GET", "/me", token_data["access_token"])
    graph_user = resp.json()
    
    # Extract user details
    email = graph_user.get("mail") or graph_user.get("userPrincipalName")
    display_name = graph_user.get("displayName", "")
    user_id = graph_user.get("id")
    
    # Check if user exists in database
    existing_user = db.query(Users).filter(Users.UserEmail == email).first()
    
    if existing_user:
        # User exists - update last login and return details
        user = existing_user
        user_type = user.UserRole
    else:
        # New user - create in database
        # Default to HR role for Microsoft authenticated users
        new_user = Users(
            UserID=user_id,
            UserName=display_name,
            UserEmail=email,
            UserRole="hr",  # Default role for Microsoft SSO users
            UserPassword=""  # No password for SSO users
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        user = new_user
        user_type = "hr"
    
    # Create JWT access token
    access_token = create_access_token(
        data={
            "sub": user.UserEmail,
            "type": user_type,
            "name": user.UserName
        }
    )
    
    # Return user details with access token
    return JSONResponse({
        "user": {
            "id": user.UserID,
            "name": user.UserName,
            "email": user.UserEmail,
            "type": user.UserRole,
            "microsoft_id": user_id,
            "display_name": display_name,
            "job_title": graph_user.get("jobTitle"),
            "mobile_phone": graph_user.get("mobilePhone"),
            "office_location": graph_user.get("officeLocation")
        },
        "access_token": access_token,
        "token_type": "bearer"
    })

def _require_account(request: Request) -> str:
    # In production, read from a real session or JWT
    # For demo, pick the first cached account
    if not user_tokens:
        raise HTTPException(401, "Sign in first at /auth/signin")
    return next(iter(user_tokens.keys()))

# ---------- SEND MAIL ----------
@router.post("/mail/send")
def send_mail(request: Request, to: str, subject: str, body_text: str):
    account_id = _require_account(request)
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
@router.post("/calendar/schedule")
def schedule_meeting(
    request: Request,
    subject: str,
    start_iso: str,
    end_iso: str,
    timezone: str = "India Standard Time",
    attendees: list[str] = [],
    teams_online: bool = True
):
    account_id = _require_account(request)
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


@router.get("/calendar/meetings")
def get_my_meetings(
    request: Request,
    top: int = 10,
    skip: int = 0
):
    '''
    Get user's calendar meetings/events.
    
    Args:
        top: Number of events to return (default: 10, max: 100)
        skip: Number of events to skip for pagination (default: 0)
    
    Returns:
        List of calendar events with details
    '''
    account_id = _require_account(request)
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


@router.get("/service/calendar/events/{user_email}")
def get_user_calendar_events(
    user_email: str,
    start_time: str = None,
    end_time: str = None,
    current_user: Users = Depends(get_current_hr_or_admin),
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
        raise HTTPException(status_code=500, detail=f"Failed to fetch calendar events: {str(e)}")


@router.post("/service/calendar/schedule")
def schedule_meeting_for_user(
    organizer_email: str,
    subject: str,
    start_iso: str,
    end_iso: str,
    attendees: list[str] = [],
    timezone: str = "UTC",
    teams_online: bool = True,
    location: str = None,
    current_user: Users = Depends(get_current_hr_or_admin),
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
        raise HTTPException(status_code=500, detail=f"Failed to schedule meeting: {str(e)}")


# ============================================
# SharePoint Connection Test
# ============================================

@router.get("/sharepoint/test-connection")
def test_sharepoint_connection():
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
            return {
                "status": "error",
                "message": "Failed to access SharePoint",
                "details": str(e),
                "configured": True,
                "authenticated": True,
                "sharepoint_configured": True
            }
            
    except Exception as e:
        logger.error(f"SharePoint connection test failed: {str(e)}")
        return {
            "status": "error",
            "message": "Connection test failed",
            "details": str(e)
        }



@router.get("/sharepoint/list-drives")
def list_sharepoint_drives():
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
        return {
            "status": "error",
            "message": "Failed to list drives",
            "details": str(e)
        }
