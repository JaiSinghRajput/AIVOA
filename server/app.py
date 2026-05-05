from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.health import router as health_router
from api.hcp import router as hcp_router
from api.interactions import router as interactions_router
from api.tools import router as tools_router
from db import init_db


app = FastAPI(title="AI-First CRM - HCP Interaction Module")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(health_router)
app.include_router(tools_router)
app.include_router(hcp_router)
app.include_router(interactions_router)
