# careers.blitzenx.com - Careers Portal

Production-ready Next.js application for candidate job applications and Thunder pre-screening intake.

## Quick Start

```bash
# Install dependencies
npm install

# Start dev server (runs on localhost:3001)
npm run dev

# Build for production
npm build

# Start production server
npm start
```

## Features

✅ **Job Listings** - Browse open positions with filters  
✅ **Thunder Chat** - Interactive candidate intake (8 questions)  
✅ **Application Status** - Track application progress  
✅ **Mobile Responsive** - Works on desktop, tablet, mobile  
✅ **Form Persistence** - Saved responses (localStorage)  

## Pages

- `/jobs` - Job listings and search
- `/apply` - Thunder chatbot intake
- `/apply/status` - Application confirmation

## Environment Variables

Create `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=BlitzenX Careers
```

## API Integration

Thunder endpoints connect to backend at `http://localhost:8000`:

- `POST /api/v1/thunder/sessions` - Create/resume session
- `POST /api/v1/thunder/sessions/{id}/answer` - Submit answer
- `POST /api/v1/thunder/sessions/{id}/submit` - Submit application

## Development

```bash
npm run dev      # Start dev server
npm run lint     # Run linter
npm run build    # Build for production
```

## Tech Stack

- Next.js 14
- React 18
- TypeScript
- Axios

## License

Proprietary - BlitzenX Inc.
