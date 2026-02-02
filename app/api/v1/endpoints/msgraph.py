
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







load_dotenv()
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = os.getenv("AUTHORITY") or f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPES = os.getenv("SCOPES").split()

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

    return RedirectResponse(url="/static/msgraph_test.html")

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
    
    response.raise_for_status()
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
