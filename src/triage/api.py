"""HTTP API: POST a ticket, get its triage back.

Run with: uvicorn triage.api:app (see the `api` service in compose.yaml).
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from triage.config import configure_logging, get_settings
from triage.models import Ticket, TriageOutput
from triage.service import TriageService, build_service


def create_app(service_factory: Callable[[], TriageService] = build_service) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        configure_logging(get_settings().log_level)
        app.state.service = service_factory()  # fails fast at startup, e.g. without an API key
        yield

    app = FastAPI(title="Support Ticket Triage Agent", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # A sync endpoint: FastAPI runs it in a worker thread, so a slow triage doesn't block others.
    @app.post("/triage")
    def triage(ticket: Ticket, request: Request) -> TriageOutput:
        service: TriageService = request.app.state.service
        return service.triage(ticket)

    return app


app = create_app()
