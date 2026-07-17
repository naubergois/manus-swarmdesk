from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_store
from app.routers import agents, approvals, board_chat, cards, chat, dashboard, projects, runtime, swarm, tickets
from app.services.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_store()
    await seed_if_empty()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(cards.router)
app.include_router(chat.router)
app.include_router(board_chat.router)
app.include_router(approvals.router)
app.include_router(agents.router)
app.include_router(swarm.router)
app.include_router(tickets.router)
app.include_router(dashboard.router)
app.include_router(runtime.router)


@app.get("/health")
async def health():
    from app.config import settings
    from app.llm import active_provider_info

    try:
        info = active_provider_info()
        llm_ready = True
    except Exception:
        info = {"provider": "none", "model": None}
        llm_ready = False
    return {
        "status": "ok",
        "service": "manus-swarmdesk",
        "llm_ready": llm_ready,
        "llm_provider": info["provider"],
        "llm_model": info["model"],
        "llm_provider_preference": settings.llm_provider,
        "orchestration": "langgraph+langchain",
        "swarm": "hierarchical-ruflo-style",
    }
