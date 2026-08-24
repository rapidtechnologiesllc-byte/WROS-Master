# HRMS Onboarding Module Backend

A comprehensive FastAPI-based backend system for managing HR onboarding processes, candidate management, interview scheduling, and authentication.

## Features

### Core Functionality
- **User Authentication & Authorization**
  - JWT-based authentication with RS256 algorithm
  - Role-based access control (Admin, HR, Candidate)
  - Secure password hashing with bcrypt
  - First-time login password change enforcement
  - Token refresh mechanism

- **Candidate Management**
  - Complete candidate profile management
  - Personal information, education, and experience tracking
  - Document management with SharePoint integration
  - Candidate assignment to jobs
  - Candidate status tracking

- **Document Management**
  - SharePoint integration for document storage
  - Document upload and verification
  - Support for PAN, Aadhar, Resume, and other documents
  - Document versioning and history
  - Virus scanning integration ready

- **Interview Management**
  - Interview panel creation and management
  - Interview scheduling with Microsoft Calendar integration
  - Feedback collection system
  - Panel member management
  - Interview analytics and reporting

- **Job Management**
  - AI-powered job description generation using Google Gemini
  - Job posting and management
  - Candidate-job assignment tracking
  - Job status management (Draft, Active, Closed)

- **Onboarding Process**
  - Multi-step onboarding workflow
  - Document verification (PAN, Aadhar)
  - Status tracking and notifications
  - Automated onboarding tasks

- **Microsoft Graph Integration**
  - Calendar access and meeting scheduling
  - SharePoint document management
  - Email notifications (ready)
  - Service account authentication
  - OAuth 2.0 flow support

## Prerequisites

- **Python**: 3.10 or higher
- **Database**: Microsoft SQL Server 2019+ or Azure SQL Database
- **ODBC Driver**: ODBC Driver 18 for SQL Server
- **Azure Account**: For Microsoft Graph integration (optional)
- **Google AI API Key**: For AI-powered job descriptions (optional)

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd OnboardingModule-Backend
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the project root:

```env
# Database Configuration
DATABASE_URL=mssql+pyodbc://username:password@server/database?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

# JWT Security Keys
JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----

# Microsoft Authentication (User-based)
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
REDIRECT_URI=https://your-app-url.com/msgraph/auth/callback
AUTHORITY=https://login.microsoftonline.com/your-tenant-id
SCOPES=https://graph.microsoft.com/.default

# Azure Service Account (Application-only)
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-app-id
AZURE_CLIENT_SECRET=your-client-secret

# SharePoint Configuration
SHAREPOINT_SITE_ID=your-site-id
SHAREPOINT_DRIVE_ID=your-drive-id
SHAREPOINT_BASE_FOLDER=candidates/2026

# Google AI (Optional)
GEMINI_API_KEY=your-gemini-api-key
```

### 5. Database Setup

#### Option 1: Using the Migration Utility (Recommended)

```bash
# Interactive mode
python migrate.py

# Or use specific commands
python migrate.py --status    # Check current status
python migrate.py --upgrade   # Upgrade to latest
python migrate.py --history   # View migration history
```

#### Option 2: Using Alembic Directly

```bash
# Check current migration
python -m alembic current

# Upgrade to latest
python -m alembic upgrade head

# View history
python -m alembic history
```

#### Option 3: Auto-initialize on Startup

```bash
# Tables will be created automatically when you run the app
python -m app.main
```

## Running the Application

### Development Mode

```bash
python -m app.main
```

The server will start at `http://localhost:8080`

### Production Mode

```bash
# Using Gunicorn with Uvicorn workers
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080

# Or using Uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

## 📚 API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### API Endpoints Overview

#### Authentication (`/api/v1/auth`)
- `POST /login` - User/Candidate login
- `POST /register` - User registration
- `POST /refresh` - Refresh access token

#### Users (`/api/v1/user`)
- `GET /users` - List all users (HR/Admin only)
- `POST /users` - Create new user (Admin only)
- `GET /users/{user_id}` - Get user details
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user

#### Candidates (`/api/v1/candidate`)
- `POST /change_password` - Change password after first login
- `GET /my-info` - Get authenticated candidate's complete profile
- `POST /candidate-form` - Submit/update candidate information
- `POST /education` - Add education details
- `POST /experience` - Add work experience
- `POST /aadhar` - Submit Aadhar details
- `POST /pan` - Submit PAN details

#### Documents (`/api/v1/documents`)
- `POST /upload` - Upload candidate document
- `GET /candidate/{candidate_id}` - Get all documents for a candidate
- `GET /{document_id}` - Get specific document details
- `PUT /{document_id}/verify` - Verify document (HR only)
- `DELETE /{document_id}` - Delete document

#### Jobs (`/api/v1/job`)
- `POST /create-job` - Create new job posting (AI-powered)
- `GET /jobs` - List all jobs
- `GET /jobs/{job_id}` - Get job details
- `PUT /jobs/{job_id}` - Update job
- `DELETE /jobs/{job_id}` - Delete job

#### Interviews (`/api/v1/interview`)
- `POST /panel` - Create interview panel
- `GET /panels` - List all panels
- `POST /schedule` - Schedule interview
- `GET /interviews` - List interviews
- `POST /feedback` - Submit interview feedback
- `GET /analytics` - Get interview analytics

#### Onboarding (`/api/v1/onboarding`)
- `POST /verify-pan` - Verify PAN card
- `POST /verify-aadhar` - Verify Aadhar card
- `GET /status/{candidate_id}` - Get onboarding status

#### Microsoft Graph (`/api/v1/msgraph`)
- `GET /auth/login` - Initiate Microsoft login
- `GET /auth/callback` - OAuth callback
- `POST /send-email` - Send email via Microsoft Graph
- `GET /calendar/events` - Get calendar events (service account)
- `POST /calendar/schedule-meeting` - Schedule meeting (service account)
- `GET /sharepoint/test` - Test SharePoint connection
- `GET /sharepoint/drives` - List SharePoint drives

## 📁 Project Structure

```
OnboardingModule-Backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/          # API route handlers
│   │       │   ├── auth.py         # Authentication endpoints
│   │       │   ├── users.py        # User management
│   │       │   ├── candidates.py   # Candidate management
│   │       │   ├── documents.py    # Document management
│   │       │   ├── interviews.py   # Interview management
│   │       │   ├── create_job.py   # Job creation (AI)
│   │       │   ├── onboarding.py   # Onboarding workflow
│   │       │   └── msgraph.py      # Microsoft Graph integration
│   │       └── routes.py           # Router aggregation
│   ├── core/
│   │   ├── config.py               # Application configuration
│   │   ├── database.py             # Database connection & utilities
│   │   ├── security.py             # Authentication & JWT
│   │   ├── logging.py              # Logging configuration
│   │   ├── dependencies.py         # FastAPI dependencies
│   │   └── graph_auth.py           # Microsoft Graph authentication
│   ├── models/
│   │   ├── base.py                 # SQLAlchemy base
│   │   ├── user.py                 # User & job models
│   │   ├── candidate.py            # Candidate models
│   │   └── document.py             # Document models
│   ├── schemas/
│   │   ├── auth.py                 # Authentication schemas
│   │   ├── user.py                 # User schemas
│   │   ├── candidate.py            # Candidate schemas
│   │   ├── interview.py            # Interview schemas
│   │   └── document.py             # Document schemas
│   ├── services/
│   │   └── document_service.py     # Document management service
│   ├── tools/
│   │   └── job_description_generator.py  # AI job description generator
│   ├── utils/
│   │   └── uniq_id_generator.py    # Unique ID generation
│   ├── middleware/
│   │   ├── __init__.py             # Middleware exports
│   │   ├── cors.py                 # CORS configuration
│   │   └── auth_middleware.py      # Authentication middleware
│   └── main.py                     # Application entry point
├── alembic/                        # Database migrations
│   ├── versions/                   # Migration scripts
│   └── env.py                      # Alembic environment
├── logs/                           # Application logs
├── static/                         # Static files
├── .env                            # Environment variables
├── requirements.txt                # Python dependencies
├── alembic.ini                     # Alembic configuration
├── migrate.py                      # Migration utility script
├── test.py                         # Pre-deployment test script
└── README.md                       # This file
```

## 🔒 Security Features

- **JWT Authentication**: RS256 algorithm with public/private key pairs
- **Password Security**: Bcrypt hashing with salt
- **CORS Protection**: Configurable CORS middleware
- **SQL Injection Prevention**: SQLAlchemy ORM with parameterized queries
- **Input Validation**: Pydantic models for request validation
- **Secure Headers**: Security headers middleware
- **Role-Based Access Control**: Fine-grained permissions
- **Audit Logging**: Comprehensive logging for sensitive operations

## Testing

```bash
# Install testing dependencies
pip install pytest pytest-asyncio httpx pytest-cov

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

## Database Migrations

### Using the Migration Utility

```bash
# Interactive mode - shows menu with options
python migrate.py

# Check current migration status
python migrate.py --status

# View migration history
python migrate.py --history

# Upgrade to latest version
python migrate.py --upgrade

# Create new migration
python migrate.py --create "description of changes"

# Show database configuration
python migrate.py --info
```

### Using Alembic Directly

```bash
# Create new migration
python -m alembic revision --autogenerate -m "description"

# Upgrade to latest
python -m alembic upgrade head

# Downgrade one version
python -m alembic downgrade -1

# Show current version
python -m alembic current

# Show history
python -m alembic history
```

## Deployment

### Azure App Service

1. Create Azure App Service (Python 3.10+)
2. Configure environment variables in Application Settings
3. Deploy using Azure CLI:
   ```bash
   az webapp up --name your-app-name --resource-group your-rg
   ```

### Docker

```dockerfile
FROM python:3.10-slim

# Install ODBC Driver
RUN apt-get update && apt-get install -y \
    curl apt-transport-https gnupg2 \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Linux Server (Production)

```bash
# 1. Clone repository
git clone <repository-url>
cd OnboardingModule-Backend

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env  # Edit with your configuration

# 5. Run migrations
python migrate.py --upgrade

# 6. Start with systemd (recommended)
sudo systemctl start onboarding-api
sudo systemctl enable onboarding-api

# Or use Gunicorn directly
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
```

##  Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | SQL Server connection string | Yes | - |
| `JWT_PRIVATE_KEY` | RSA private key for JWT signing | Yes | - |
| `JWT_PUBLIC_KEY` | RSA public key for JWT verification | Yes | - |
| `TENANT_ID` | Azure AD tenant ID | No* | - |
| `CLIENT_ID` | Azure AD application ID | No* | - |
| `CLIENT_SECRET` | Azure AD client secret | No* | - |
| `AZURE_TENANT_ID` | Azure service account tenant ID | No* | - |
| `AZURE_CLIENT_ID` | Azure service account client ID | No* | - |
| `AZURE_CLIENT_SECRET` | Azure service account secret | No* | - |
| `SHAREPOINT_SITE_ID` | SharePoint site ID | No* | - |
| `SHAREPOINT_DRIVE_ID` | SharePoint drive ID | No* | - |
| `GEMINI_API_KEY` | Google Gemini API key | No** | - |

*Required only if using Microsoft Graph integration  
**Required only if using AI job description generation

### Logging

Logs are stored in the `logs/` directory with daily rotation:
- Format: `app_YYYYMMDD.log`
- Level: INFO (configurable)
- Includes request/response logging
- Audit logs for sensitive operations


## Authors

**Suresh Kannan**  
AI Developer  
Blitzenx

## Version History

### v1.1.0 (Latest)
- ✅ Added comprehensive document management with SharePoint integration
- ✅ Implemented Microsoft Graph calendar and meeting scheduling
- ✅ Added migration utility script (`migrate.py`)
- ✅ Fixed Alembic configparser interpolation issues
- ✅ Added audit logging for Microsoft Graph services
- ✅ Improved security with comprehensive input validation

### v1.0.0
- Initial release
- User authentication and authorization
- Candidate management
- Interview scheduling
- Job management with AI integration
- Onboarding workflow
- Microsoft Graph integration

## Roadmap

- [ ] Email notification system via Microsoft Graph
- [ ] Advanced analytics dashboard
- [ ] Mobile app integration
- [ ] Multi-language support
- [ ] Advanced reporting features
- [ ] LinkedIn job posting integration
- [ ] Automated interview scheduling
- [ ] Video interview integration

## Tech Stack

- **Framework**: FastAPI 0.115+
- **Database**: Microsoft SQL Server 2019+ / Azure SQL
- **ORM**: SQLAlchemy 2.0+
- **Authentication**: PyJWT with RS256
- **AI Integration**: Google Gemini via LangChain
- **Microsoft Integration**: MSAL, Microsoft Graph API
- **Server**: Uvicorn (development), Gunicorn (production)

---

Made with care for efficient HR onboarding

