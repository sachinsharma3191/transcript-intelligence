"""FastAPI backend for the pipeline demo. One endpoint group per assignment step.

Run locally from the project root:

    ./.venv/bin/uvicorn api:app --app-dir src --reload --port 8000

    GET  /api/health              liveness check
    GET  /api/data                step 1: what was loaded
    POST /api/runs                run the pipeline with the current config
    GET  /api/runs/latest         last run summary (includes changes vs the run before)
    GET  /api/categories          step 2: themes, keywords, examples
    GET  /api/sentiment           step 3: sentiment by call type, theme, side, time
    GET  /api/insights            step 4: churn, feature demand, competitor, repeat support
    GET  /api/calls               step 4 drill-down: filter calls by theme, type, account
    GET  /api/config              current config
    PUT  /api/config              replace config (validated, 422 on bad input)
    POST /api/config/reset        restore defaults
"""
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pipeline import NoRunYet, Pipeline

DONE_STATUSES = {"open", "done"}

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("api")

pipeline = None
lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    global pipeline
    start = time.perf_counter()
    pipeline = Pipeline()  # loads the dataset and scores VADER once, at startup
    log.info("startup complete: %d meetings loaded in %.0f ms",
             len(pipeline.meetings), (time.perf_counter() - start) * 1000)
    yield
    log.info("shutdown")


app = FastAPI(title="Transcript Intelligence pipeline API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConfigIn(BaseModel):
    title_weight: int = Field(ge=1, le=10)
    outage_date: str = Field(description="ISO date, e.g. 2026-03-10")
    themes: dict[str, list[str]]


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    log.info("%s %s -> %d (%.1f ms)", request.method, request.url.path, response.status_code, ms)
    return response


@app.exception_handler(NoRunYet)
def _no_run(_, exc: NoRunYet):
    log.warning("step requested before a run: %s", exc)
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(Exception)
def _unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal error, see server log"})


@app.get("/api/health")
def health():
    return {"status": "ok", "meetings": len(pipeline.meetings)}


# recommendations
@app.get("/api/recommendations/churn")
def rec_churn():
    return pipeline.rec_churn()


@app.get("/api/recommendations/weekly")
def rec_weekly():
    return pipeline.rec_weekly()


@app.get("/api/recommendations/roadmap")
def rec_roadmap():
    return pipeline.rec_roadmap()


@app.get("/api/recommendations/actions")
def rec_actions():
    return pipeline.rec_actions()


class ActionStatus(BaseModel):
    status: str


@app.put("/api/recommendations/actions/{action_id}")
def set_action(action_id: str, body: ActionStatus):
    if body.status not in DONE_STATUSES:
        raise HTTPException(status_code=422, detail="status must be open or done")
    try:
        return pipeline.set_action_status(action_id, body.status)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no action item {action_id}")


# step 1
@app.get("/api/data")
def data():
    return pipeline.load_summary()


# config
@app.get("/api/config")
def get_config():
    return pipeline.get_config()


@app.put("/api/config")
def put_config(body: ConfigIn):
    with lock:
        try:
            cfg = pipeline.set_config(body.model_dump())
        except ValueError as exc:
            log.warning("config rejected: %s", exc)
            raise HTTPException(status_code=422, detail=str(exc))
        log.info("config updated: %d themes, title_weight=%d, outage=%s",
                 len(cfg["themes"]), cfg["title_weight"], cfg["outage_date"])
        return cfg


@app.post("/api/config/reset")
def reset_config():
    with lock:
        log.info("config reset to defaults")
        return pipeline.reset_config()


# run
@app.post("/api/runs")
def create_run():
    with lock:
        result = pipeline.run()
        log.info("run #%d done in %.0f ms: %d calls, %d calls moved theme",
                 result["run"], result["duration_ms"], len(result["meetings"]),
                 len(result["changes"]["moved_meetings"]))
        return result


@app.get("/api/runs/latest")
def latest_run():
    if pipeline.latest is None:
        raise HTTPException(status_code=404, detail="no run yet; POST /api/runs first")
    return pipeline.latest


# step 2, 3, 4
@app.get("/api/categories")
def categories():
    return pipeline.categories()


@app.get("/api/sentiment")
def sentiment_view():
    return pipeline.sentiment_view()


@app.get("/api/insights")
def insights_view():
    return pipeline.insights_view()


@app.get("/api/calls")
def calls(theme: str | None = None, call_type: str | None = None,
          account: str | None = None, limit: int = 50):
    return pipeline.calls(theme=theme, call_type=call_type, account=account,
                          limit=min(max(limit, 1), 200))
