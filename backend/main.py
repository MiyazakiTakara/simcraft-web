import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
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

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(simulation.router)
app.include_router(results.router)
app.include_router(history.router)
app.include_router(rankings.router)
app.include_router(reactions.router)
app.include_router(characters.router)

app.mount("/", StaticFiles(directory="/app/frontend", html=True), name="static")
