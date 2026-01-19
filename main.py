# main.py
from fastapi import FastAPI, Depends, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from typing import Optional
from routes import router
from microsoft import ms_graph_router


app = FastAPI(title="Onboarding Auth API")

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    """Create database tables if they don't exist"""
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables initialized")

# set appropriate origins for your frontend dev server
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # add your deployed frontend domain here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)
app.include_router(ms_graph_router,prefix="/msgraph")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home():
    return {"status": "Onboarding Auth API", "msgraph_test": "/static/msgraph_test.html"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8080,
        reload=True
    )