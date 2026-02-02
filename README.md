# HRMS Onboarding Module Backend

A comprehensive FastAPI-based backend system for managing HR onboarding processes, candidate management, interview scheduling, and authentication.

## Features

### Core Functionality
- **User Authentication & Authorization**
  - JWT-based authentication with RS256 algorithm
  - Role-based access control (Admin, HR, Candidate)
  - Secure password hashing with bcrypt
  - First-time login password change enforcement

- **Candidate Management**
  - Complete candidate profile management
  - Personal information, education, and experience tracking
  - Document management (PAN, Aadhar)
  - Candidate assignment to jobs

- **Interview Management**
  - Interview panel creation and management
  - Interview scheduling and tracking
  - Feedback collection system
  - Panel member management

- **Job Management**
  - AI-powered job description generation using Google Gemini
  - Job posting and management
  - Candidate-job assignment tracking

- **Onboarding Process**
  - Document verification (PAN, Aadhar)
  - Multi-step onboarding workflow
  - Status tracking and notifications

- **Microsoft Integration**
  - Microsoft Graph API integration
  - Azure AD authentication support
  - Email notifications via Microsoft Graph

## Prerequisites

- **Python**: 3.10 or higher
- **Database**: Microsoft SQL Server 2019+ or Azure SQL Database
- **ODBC Driver**: ODBC Driver 17 for SQL Server
- **Azure Account**: For Microsoft Graph integration (optional)

## Installation

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

Create a `.env` file in the project root. See [SIMPLE_SETUP_GUIDE.md](SIMPLE_SETUP_GUIDE.md) for detailed instructions.

**Minimum required variables:**

```env
# Database Connection
DATABASE_URL=mssql+pyodbc://USERNAME@SERVERNAME:PASSWORD@SERVERNAME.database.windows.net/DBNAME?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30

# JWT Security
JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----

# Microsoft Authentication (Optional)
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
REDIRECT_URI=https://your-app-url.com/msgraph/auth/callback
AUTHORITY=https://login.microsoftonline.com/your-tenant-id
SCOPES=User.Read Mail.Send
```

### 5. Database Setup

```bash
# Initialize database tables
python -m app.main

# Or use Alembic for migrations
alembic upgrade head
```

## Running the Application

### Development Mode

```bash
python -m app.main
```

The server will start at `http://localhost:8000`

### Production Mode

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### API Endpoints Overview

#### Authentication (`/api/v1/auth`)
- `POST /login` - User/Candidate login
- `POST /register` - User registration
- `POST /refresh` - Refresh access token

#### Users (`/api/v1/user`)
- `GET /users` - List all users
- `POST /users` - Create new user
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

#### Jobs (`/api/v1/job`)
- `POST /create-job` - Create new job posting (AI-powered)
- `GET /jobs` - List all jobs
- `GET /jobs/{job_id}` - Get job details

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

## Project Structure

```
OnboardingModule-Backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/          # API route handlers
│   │       │   ├── auth.py
│   │       │   ├── users.py
│   │       │   ├── candidates.py
│   │       │   ├── interviews.py
│   │       │   ├── create_job.py
│   │       │   ├── onboarding.py
│   │       │   └── msgraph.py
│   │       └── routes.py           # Router aggregation
│   ├── core/
│   │   ├── config.py               # Application configuration
│   │   ├── database.py             # Database connection & utilities
│   │   ├── security.py             # Authentication & security
│   │   └── logging.py              # Logging configuration
│   ├── models/
│   │   ├── base.py                 # SQLAlchemy base
│   │   ├── user.py                 # User & job models
│   │   └── candidate.py            # Candidate models
│   ├── schemas/
│   │   ├── auth.py                 # Authentication schemas
│   │   ├── user.py                 # User schemas
│   │   └── candidate.py            # Candidate schemas
│   ├── middleware/                 # Custom middleware
│   └── main.py                     # Application entry point
├── alembic/                        # Database migrations
├── logs/                           # Application logs
├── static/                         # Static files
├── .env                            # Environment variables
├── requirements.txt                # Python dependencies
├── alembic.ini                     # Alembic configuration
├── DATABASE_SCHEMA.md              # Database schema documentation
├── SIMPLE_SETUP_GUIDE.md           # Detailed setup guide
└── README.md                       # This file
```

## Security Features

- **JWT Authentication**: RS256 algorithm with public/private key pairs
- **Password Security**: Bcrypt hashing with salt
- **CORS Protection**: Configurable CORS middleware
- **SQL Injection Prevention**: SQLAlchemy ORM with parameterized queries
- **Input Validation**: Pydantic models for request validation
- **Secure Headers**: Security headers middleware

## Testing

```bash
# Install testing dependencies
pip install pytest pytest-asyncio httpx pytest-cov

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## Database Schema

See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for complete database schema documentation including:
- Table structures
- Relationships
- Indexes
- Constraints

## Configuration

### Application Settings

Configure via environment variables or `.env` file:

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | SQL Server connection string | Yes |
| `JWT_PRIVATE_KEY` | RSA private key for JWT signing | Yes |
| `JWT_PUBLIC_KEY` | RSA public key for JWT verification | Yes |
| `TENANT_ID` | Azure AD tenant ID | No* |
| `CLIENT_ID` | Azure AD application ID | No* |
| `CLIENT_SECRET` | Azure AD client secret | No* |
| `REDIRECT_URI` | OAuth redirect URI | No* |

*Required only if using Microsoft Graph integration

### Logging

Logs are stored in the `logs/` directory with daily rotation:
- Format: `app_YYYYMMDD.log`
- Level: INFO (configurable)
- Includes request/response logging

## Deployment

### Azure App Service

1. Create Azure App Service (Python 3.10+)
2. Configure environment variables in Application Settings
3. Deploy using:
   ```bash
   az webapp up --name your-app-name --resource-group your-rg
   ```

### Docker (Optional)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Authors

Suresh Kannan
AI Developer
Blitzenx

## Version History

- **v1.0.0** - Initial release
  - User authentication and authorization
  - Candidate management
  - Interview scheduling
  - Job management with AI integration
  - Onboarding workflow
  - Microsoft Graph integration

## Roadmap

- [ ] Email notification system
- [ ] Advanced analytics dashboard
- [ ] Document upload and storage
- [ ] Mobile app integration
- [ ] Multi-language support
- [ ] Advanced reporting features

## Tech Stack

- **Framework**: FastAPI 0.115+
- **Database**: Microsoft SQL Server / Azure SQL
- **ORM**: SQLAlchemy 2.0+
- **Authentication**: PyJWT with RS256
- **AI Integration**: Google Gemini via LangChain
- **Microsoft Integration**: MSAL, Microsoft Graph API
- **Server**: Uvicorn (development), Gunicorn (production)

---

Made with care for efficient HR onboarding

