import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from traffic import TrafficMiddleware

import admin
import auth
import simulation
import results
import history
import rankings
import reactions
import characters
import profiles
import favorites
import icons

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrafficMiddleware)

@app.on_event("startup")
async def startup():
    init_db()
    favorites.ensure_table()

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(simulation.router)
app.include_router(results.router)
app.include_router(history.router)
app.include_router(rankings.router)
app.include_router(reactions.router)
app.include_router(characters.router)
app.include_router(profiles.router)
app.include_router(favorites.router)
app.include_router(icons.router)

# Publiczny endpoint wygladu
@app.get("/api/appearance")
async def public_appearance():
    return admin.load_appearance_config()

@app.get("/rankings")
async def page_rankings():
    return FileResponse("/app/frontend/rankings.html")

@app.get("/result/{job_id}")
async def page_result(job_id: str):
    return FileResponse("/app/frontend/result.html")

@app.get("/u/{bnet_id}")
async def page_user_profile(bnet_id: str):
    return FileResponse("/app/frontend/profile.html")

app.mount("/", StaticFiles(directory="/app/frontend", html=True), name="static")
