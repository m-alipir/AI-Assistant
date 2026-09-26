"""Local-only operational API plus a small server-rendered admin UI."""

import json
import logging
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from inspect import isawaitable
from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.briefing.presentation import (
    BRIEFING_SECTIONS,
    BriefingViewItem,
    compact_sentences,
    format_istanbul,
    legacy_sections,
    safe_links,
    shown_because,
)
from app.config.bulk_urls import (
    BulkUrlLimitExceeded,
    BulkUrlRepositoryUnavailable,
    BulkUrlService,
    InvalidBulkUrlStructure,
)
from app.config.csv_import import (
    CsvImportService,
    CsvLimitExceeded,
    CsvRepositoryUnavailable,
    InvalidCsvStructure,
    MalformedCsv,
)
from app.config.onboarding import SchedulerPreference
from app.config.opml import (
    InvalidOpmlStructure,
    MalformedOpml,
    OpmlLimitExceeded,
    OpmlRepositoryUnavailable,
    OpmlService,
)
from app.config.source_export import SourceExportRepositoryUnavailable, SourceExportService
from app.config.source_pack import (
    InvalidSourcePackStructure,
    MalformedSourcePack,
    SourcePackLimitExceeded,
    SourcePackRepositoryUnavailable,
    SourcePackService,
)
from app.config.source_repository import (
    EnabledSourceDeleteBlocked,
    ManagedSourceCreate,
    ManagedSourceUpdate,
    SourceAlreadyExists,
    SourceNotFound,
    SourceRepository,
)
from app.email.oauth import OAuthErrorCategory, OAuthFlowError
from app.interests.feedback import record_briefing_feedback
from app.knowledge.search import KnowledgeSearchError, SearchFilters, SearchResponse

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
MODEL_ROLES = ("gatekeeper", "extractor", "reasoner", "editor", "embedding")
logger = logging.getLogger(__name__)
OAUTH_FAILURE_MESSAGES: dict[OAuthErrorCategory, str] = {
    "oauth_state_invalid_or_expired": (
        "Bağlantı süresi doldu veya doğrulama geçersiz. Admin panelinden bağlantıyı yeniden "
        "başlatın."
    ),
    "token_exchange_invalid_client": (
        "Google OAuth Client ID ve Client Secret ayarlarını kontrol edin; ardından yeniden deneyin."
    ),
    "token_exchange_redirect_mismatch": (
        "Google Cloud Console'daki Authorized redirect URI, GMAIL_OAUTH_REDIRECT_URI ile "
        "karakter karakter aynı olmalıdır."
    ),
    "token_exchange_upstream_http_error": (
        "Google token endpoint isteği tamamlanamadı. Bağlantıyı yeniden başlatın; sorun sürerse "
        "sunucu ağ erişimini kontrol edin."
    ),
    "refresh_token_missing": (
        "Google yenileme tokenı göndermedi. Bağlantıyı yeniden başlatın ve Google izin "
        "ekranındaki erişimi onaylayın."
    ),
    "token_storage_error": (
        "Token güvenli biçimde kaydedilemedi. APP_ENCRYPTION_KEY yapılandırmasını kontrol edip "
        "bağlantıyı yeniden başlatın."
    ),
}


def _oauth_failure_response(category: OAuthErrorCategory) -> HTMLResponse:
    """Return safe local-admin guidance without exposing OAuth/provider data."""
    logger.warning("gmail_oauth_callback_failed", extra={"oauth_error_category": category})
    message = OAUTH_FAILURE_MESSAGES[category]
    return HTMLResponse(
        "<h1>Gmail bağlantısı tamamlanamadı</h1>"
        f"<p>{message}</p>"
        f"<p>Tanılama kodu: <code>{category}</code></p>"
        "<p><a href='/admin'>Admin paneline dön</a></p>",
        status_code=400,
    )


class ModelUpdate(BaseModel):
    role: str
    model: str = Field(min_length=1, max_length=256)


class YouTubeLanguageUpdate(BaseModel):
    language: Literal["tr", "en"] | None = None


class SourcePackUpload(BaseModel):
    yaml: str = Field(min_length=1)


class OpmlUpload(BaseModel):
    opml: str = Field(min_length=1)


class CsvUpload(BaseModel):
    csv: str = Field(min_length=1)


class BulkUrlUpload(BaseModel):
    urls: str = Field(min_length=1)


class BriefingFeedback(BaseModel):
    """One intentionally small, safe preference signal from a rendered briefing item."""

    action: str = Field(pattern="^(more|less|not_useful)$")


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise HTTPException(500, "admin configuration root must be a mapping")
    return data


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    """Atomically replace trusted configuration so readers never observe a partial document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            yaml.safe_dump(data, output, sort_keys=False, allow_unicode=True)
        os.replace(temporary_name, path)
    except OSError:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _source_repository(request: Request) -> SourceRepository:
    repository = getattr(request.app.state, "source_repository", None)
    if repository is None:
        raise HTTPException(503, "managed source repository is unavailable")
    return repository


def _source_view(row: dict[str, object]) -> dict[str, object]:
    """Expose only the non-secret managed-source projection used by Admin."""
    return {
        "id": row["id"],
        "kind": row["kind"],
        "name": row["name"],
        "endpoint": row["canonical_endpoint"],
        "stream": row["stream"],
        "enabled": row["enabled"],
        "priority": row["priority"],
        "category": row["category"],
        "language": row["language"],
        "freshness_hours": row["freshness_hours"],
        "health_status": row["health_status"],
        "last_attempt_at": row["last_attempt_at"],
        "last_success_at": row["last_success_at"],
        "consecutive_failures": row["consecutive_failures"],
        "last_error_category": row["last_error_category"],
        "next_retry_at": row["next_retry_at"],
        "last_successful_strategy": row["last_successful_strategy"],
        "detected_language": row["detected_language"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _raise_source_http_error(error: Exception) -> None:
    if isinstance(error, SourceAlreadyExists):
        raise HTTPException(409, "source endpoint is already managed") from error
    if isinstance(error, SourceNotFound):
        raise HTTPException(404, "managed source not found") from error
    if isinstance(error, EnabledSourceDeleteBlocked):
        raise HTTPException(409, "disable the source before deleting it") from error
    if isinstance(error, ValueError):
        raise HTTPException(422, str(error)) from error
    raise error


def _raise_source_pack_http_error(error: Exception) -> None:
    if isinstance(error, MalformedSourcePack):
        raise HTTPException(400, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, SourcePackLimitExceeded):
        raise HTTPException(413, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, InvalidSourcePackStructure):
        raise HTTPException(422, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, SourcePackRepositoryUnavailable):
        raise HTTPException(503, "managed source repository is unavailable") from error
    raise error


def _raise_opml_http_error(error: Exception) -> None:
    if isinstance(error, MalformedOpml):
        raise HTTPException(400, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, OpmlLimitExceeded):
        raise HTTPException(413, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, InvalidOpmlStructure):
        raise HTTPException(422, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, OpmlRepositoryUnavailable):
        raise HTTPException(503, "managed source repository is unavailable") from error
    raise error


def _raise_delimited_import_http_error(error: Exception) -> None:
    if isinstance(error, MalformedCsv):
        raise HTTPException(400, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, (CsvLimitExceeded, BulkUrlLimitExceeded)):
        raise HTTPException(413, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, (InvalidCsvStructure, InvalidBulkUrlStructure)):
        raise HTTPException(422, {"code": error.code, "message": str(error)}) from error
    if isinstance(error, (CsvRepositoryUnavailable, BulkUrlRepositoryUnavailable)):
        raise HTTPException(503, "managed source repository is unavailable") from error
    raise error


async def _queue_imported_category_questions(
    request: Request, result: dict[str, object]
) -> None:
    """Immediately ask about at most three new ambiguous imports; the DB scan handles the rest."""
    queue_question = getattr(request.app.state, "queue_source_category_question", None)
    sources = result.get("sources")
    if not callable(queue_question) or not isinstance(sources, list):
        return
    queued = 0
    for item in sources:
        if not isinstance(item, dict) or item.get("status") != "created":
            continue
        source = item.get("source")
        source_id = item.get("source_id")
        if not isinstance(source, dict) or source.get("category") is not None:
            continue
        if not isinstance(source_id, str) or not source_id:
            continue
        try:
            result_status = await queue_question(source_id)
        except Exception:
            logger.warning(
                "admin_source_category_question_failed",
                extra={"diagnostic_category": "category_question_queue_unavailable"},
            )
            break
        queued += 1
        if result_status == "failed" or queued >= 3:
            break


async def _admin_sources(request: Request) -> list[dict[str, object]]:
    repository = _source_repository(request)
    try:
        rows = await repository.list()
    except Exception:
        raise HTTPException(503, "managed source repository is unavailable") from None
    return [_source_view(row) for row in rows]


async def _database_details(request: Request) -> dict[str, Any]:
    empty = {
        "migration": "unavailable",
        "events": [],
        "interest_rows": [],
        "llm_recent": [],
        "briefings": [],
        "gmail_accounts": [],
        "blocked_youtube": [],
        "scheduled_runs": [],
        "error": None,
    }
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return empty
    try:
        async with engine.connect() as connection:
            migration = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar()
            events = (
                (
                    await connection.execute(
                        text(
                            "SELECT canonical_title, occurred_at, status FROM events "
                            "ORDER BY occurred_at DESC LIMIT 10"
                        )
                    )
                )
                .mappings()
                .all()
            )
            calls = (
                (
                    await connection.execute(
                        text(
                            "SELECT role, model_id, status, estimated_cost_usd, provider_cost_usd, "
                            "cost_status, created_at "
                            "FROM llm_calls ORDER BY created_at DESC LIMIT 10"
                        )
                    )
                )
                .mappings()
                .all()
            )
            briefings = (
                (
                    await connection.execute(
                        text(
                            "SELECT id, rendered, created_at FROM briefings "
                            "ORDER BY created_at DESC LIMIT 10"
                        )
                    )
                )
                .mappings()
                .all()
            )
            interest_rows = (
                (
                    await connection.execute(
                        text("SELECT subject, base, explicit, adaptive FROM interest_profile")
                    )
                )
                .mappings()
                .all()
            )
            gmail_accounts = (
                (await connection.execute(text("SELECT id, last_sync_at FROM gmail_accounts")))
                .mappings()
                .all()
            )
            blocked_youtube = (
                (
                    await connection.execute(
                        text(
                            "SELECT content_hash, source_name, title, published_at, "
                            "failure_category, created_at, updated_at, retry_state "
                            "FROM post_llm_failures WHERE source_kind = 'youtube' "
                            "ORDER BY updated_at DESC NULLS LAST, "
                            "created_at DESC LIMIT 25"
                        )
                    )
                )
                .mappings()
                .all()
            )
            scheduled_runs = (
                (
                    await connection.execute(
                        text(
                            "SELECT run_date, started_at, completed_at, status, message "
                            "FROM (SELECT run_date, started_at, completed_at, status, message "
                            "FROM scheduled_run_slots UNION ALL "
                            "SELECT old.run_date, old.started_at, old.completed_at, "
                            "old.status, old.message FROM scheduled_runs old "
                            "WHERE NOT EXISTS (SELECT 1 FROM scheduled_run_slots current "
                            "WHERE current.run_date = old.run_date "
                            "AND current.started_at = old.started_at)) history "
                            "ORDER BY started_at DESC LIMIT 10"
                        )
                    )
                )
                .mappings()
                .all()
            )
        return {
            "migration": migration or "unknown",
            "events": [dict(row) for row in events],
            "interest_rows": [dict(row) for row in interest_rows],
            "llm_recent": [dict(row) for row in calls],
            "briefings": [dict(row) for row in briefings],
            "gmail_accounts": [dict(row) for row in gmail_accounts],
            "blocked_youtube": [dict(row) for row in blocked_youtube],
            "scheduled_runs": [dict(row) for row in scheduled_runs],
            "error": None,
        }
    except Exception:
        return {**empty, "error": "unavailable"}


async def _dashboard_context(request: Request) -> dict[str, Any]:
    try:
        sources = await _admin_sources(request)
    except HTTPException as error:
        if error.status_code != 503:
            raise
        sources = []
    models = _load_yaml(request.app.state.models_path)
    roles = models.get("roles", {}) if isinstance(models.get("roles"), dict) else {}
    database_ready = await request.app.state.readiness_check()
    openrouter_configured = bool(getattr(request.app.state, "openrouter_configured", False))
    configured_models = all(
        isinstance(roles.get(role), dict)
        and str(roles[role].get("model", "")).strip()
        and not str(roles[role]["model"]).startswith("REPLACE_")
        for role in MODEL_ROLES
    )
    usable_source = any(
        item["enabled"] and not str(item["endpoint"]).upper().startswith("REPLACE")
        for item in sources
    )
    runtime_job_connected = callable(getattr(request.app.state, "run_callback", None))
    scheduler = getattr(request.app.state, "scheduler", None)
    return {
        "request": request,
        # The source form is outside its table loop; an empty value keeps that optional selector
        # independent from the last configured source.
        "source": {"language": None},
        "sources": sources,
        "interests": _load_yaml(request.app.state.interests_path),
        "model_rows": [
            {"role": role, "model": roles.get(role, {}).get("model", "not configured")}
            for role in MODEL_ROLES
        ],
        "details": await _database_details(request),
        "database_ready": database_ready,
        "openrouter_configured": openrouter_configured,
        "gmail_configured": bool(
            getattr(request.app.state, "gmail_configured", False)
            and getattr(request.app.state, "gmail_encryption_ready", False)
        ),
        "active_sources": sum(item["enabled"] for item in sources),
        "models_configured": configured_models,
        "runtime_job_connected": runtime_job_connected,
        "first_test_ready": database_ready
        and openrouter_configured
        and configured_models
        and usable_source
        and runtime_job_connected,
        "last_run": getattr(request.app.state, "last_run", "idle"),
        "last_run_details": getattr(request.app.state, "last_run_details", None),
        "scheduler": scheduler.state if scheduler else None,
    }


async def _control_center_context(request: Request) -> dict[str, Any]:
    """Build the small, non-sensitive context shared by Control Center pages."""
    try:
        sources = await _admin_sources(request)
    except HTTPException as error:
        if error.status_code != 503:
            raise
        sources = []
        sources_available = False
    else:
        sources_available = True
    scheduler = getattr(request.app.state, "scheduler", None)
    database_ready = await request.app.state.readiness_check()
    details = await _database_details(request)
    try:
        metrics = await request.app.state.metrics_provider()
    except Exception:
        metrics = {"llm_calls": None, "llm_cost_usd": None, "recent_briefings": []}
    failures = sorted(
        (source for source in sources if source["last_error_category"]),
        key=lambda source: str(source["last_attempt_at"] or ""),
        reverse=True,
    )[:5]
    latest_briefing = details["briefings"][0] if details["briefings"] else None
    source_counts = {
        "total": len(sources),
        "enabled": sum(item["enabled"] for item in sources),
        "unhealthy": sum(item["health_status"] != "healthy" for item in sources),
        "cooling_down": sum(item["next_retry_at"] is not None for item in sources),
    }
    return {
        "request": request,
        "sources": sources,
        "database_ready": database_ready,
        "sources_available": sources_available,
        "active_sources": source_counts["enabled"],
        "disabled_sources": source_counts["total"] - source_counts["enabled"],
        "source_counts": source_counts,
        "recent_source_failures": failures,
        "details": details,
        "latest_briefing": latest_briefing,
        "provider_usage": {
            "llm_calls": metrics.get("llm_calls"),
            "llm_cost_usd": metrics.get("llm_cost_usd"),
        },
        "provider_configured": bool(getattr(request.app.state, "openrouter_configured", False)),
        "last_run": getattr(request.app.state, "last_run", "idle"),
        "last_run_details": getattr(request.app.state, "last_run_details", None),
        "overall_status": "ready"
        if database_ready and sources_available and source_counts["enabled"]
        else "attention",
        "telegram_configured": bool(
            getattr(request.app.state, "telegram_webhook_handler", None)
            or getattr(request.app.state, "telegram_polling", None)
            or (
                getattr(request.app.state, "telegram_enabled", False)
                and getattr(request.app.state, "telegram_mode", None) == "polling"
            )
        ),
        "gmail_configured": bool(
            getattr(request.app.state, "gmail_configured", False)
            and getattr(request.app.state, "gmail_encryption_ready", False)
        ),
        "scheduler": scheduler.state if scheduler else None,
    }


async def _control_center_scheduler_context(request: Request) -> dict[str, object]:
    """Read the existing persisted scheduler preference and bounded runtime status."""
    context = await _control_center_context(request)
    repository = getattr(request.app.state, "onboarding_repository", None)
    scheduler = getattr(request.app.state, "scheduler", None)
    preference: SchedulerPreference | None = None
    error: str | None = None
    if repository is None or scheduler is None:
        error = "unavailable"
    else:
        try:
            preference = await repository.scheduler_preference()
        except Exception:
            logger.warning("control_center_scheduler_preference_read_failed")
            error = "unavailable"
    return {
        "request": request,
        "scheduler": scheduler.state if scheduler else None,
        "preference": preference,
        "history": context["details"]["scheduled_runs"],
        "history_error": context["details"]["error"],
        "unavailable": error is not None,
    }


def _control_center_briefing_view(row: Mapping[str, object]) -> dict[str, object]:
    """Build a bounded, escaped-template-ready view of one persisted briefing."""
    rendered = str(row.get("rendered") or "")
    created_at = row.get("created_at")
    timestamp = format_istanbul(created_at) if isinstance(created_at, datetime) else None
    return {
        "id": str(row.get("id") or ""),
        "created_at": timestamp,
        "rendered": rendered,
        "status": "Saved" if rendered.strip() else "Incomplete",
        "summary": compact_sentences(rendered, limit=1, max_chars=240)
        if rendered.strip()
        else "Generated content is unavailable for this saved record.",
    }


def _control_center_search_event_view(event: object) -> dict[str, object]:
    """Prepare the existing compact search projection for escaped Control Center rendering."""
    occurred_at = getattr(event, "occurred_at", None)
    return {
        "id": str(getattr(event, "event_id", "")),
        "title": str(getattr(event, "title", "")),
        "occurred_at": format_istanbul(occurred_at) if isinstance(occurred_at, datetime) else None,
        "source_links": safe_links(list(getattr(event, "source_links", []))),
        "verified_facts": list(getattr(event, "verified_facts", [])),
        "stored_inferences": list(getattr(event, "stored_inferences", [])),
        "category_paths": list(getattr(event, "category_paths", [])),
        "entities": list(getattr(event, "entities", [])),
        "topics": list(getattr(event, "topics", [])),
    }


async def _control_center_search_event(request: Request, event_id: str) -> dict[str, object]:
    """Read a single previously retrieved event without running search or a model."""
    callback = getattr(request.app.state, "search_event_detail_callback", None)
    if not callable(callback):
        return {"item": None, "error": "unavailable"}
    try:
        event = await callback(event_id)
    except KnowledgeSearchError as error:
        logger.warning(
            "control_center_memory_detail_read_failed",
            extra={"search_error_category": error.category},
        )
        return {"item": None, "error": "unavailable"}
    except Exception:
        logger.exception(
            "control_center_memory_detail_read_failed",
            extra={"search_error_category": "search_unexpected_error"},
        )
        return {"item": None, "error": "unavailable"}
    return {
        "item": _control_center_search_event_view(event) if event is not None else None,
        "error": None,
    }


async def _control_center_briefing_history(request: Request) -> dict[str, object]:
    """Read a small, newest-first history without invoking briefing generation."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return {"items": [], "error": "unavailable"}
    try:
        async with engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT id, created_at, rendered FROM briefings "
                            "ORDER BY created_at DESC LIMIT 50"
                        )
                    )
                )
                .mappings()
                .all()
            )
    except Exception:
        logger.warning("control_center_briefing_history_read_failed")
        return {"items": [], "error": "unavailable"}
    return {"items": [_control_center_briefing_view(row) for row in rows], "error": None}


async def _control_center_briefing(request: Request, briefing_id: str) -> dict[str, object]:
    """Read one persisted briefing for the Control Center without reprocessing it."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return {"item": None, "error": "unavailable"}
    try:
        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT id, created_at, rendered FROM briefings "
                            "WHERE id = :id"
                        ),
                        {"id": briefing_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
    except Exception:
        logger.warning("control_center_briefing_read_failed")
        return {"item": None, "error": "unavailable"}
    return {
        "item": _control_center_briefing_view(row) if row is not None else None,
        "error": None,
    }


@router.get("/status")
async def status(request: Request) -> dict[str, object]:
    metrics = await request.app.state.metrics_provider()
    return {
        "status": "ok",
        "run_now": getattr(request.app.state, "last_run", "idle"),
        "errors": [],
        **metrics,
    }


@router.get("/briefings")
async def briefings(request: Request) -> dict[str, object]:
    metrics = await request.app.state.metrics_provider()
    return {"items": metrics["recent_briefings"]}


@router.post("/search")
async def search_ask(filters: SearchFilters, request: Request) -> dict[str, object]:
    """Run bounded user search without accepting or returning raw email/provider payloads."""
    callback = getattr(request.app.state, "ask_callback", None)
    if not callable(callback):
        raise HTTPException(503, "knowledge search is unavailable in this deployment")
    try:
        return await callback(filters)
    except KnowledgeSearchError as error:
        logger.warning(
            "knowledge_search_failed", extra={"search_error_category": error.category}
        )
        return _search_unavailable_response(error.category)
    except Exception:
        logger.exception(
            "knowledge_search_failed", extra={"search_error_category": "search_unexpected_error"}
        )
        return _search_unavailable_response("search_unexpected_error")


@router.post("/search/retrieve")
async def search_retrieve(filters: SearchFilters, request: Request) -> dict[str, object]:
    """Return existing deterministic memory retrieval without a provider call."""
    callback = getattr(request.app.state, "search_callback", None)
    if not callable(callback):
        raise HTTPException(503, "memory search is unavailable in this deployment")
    try:
        return await callback(filters)
    except KnowledgeSearchError as error:
        logger.warning(
            "admin_memory_search_failed", extra={"search_error_category": error.category}
        )
        raise HTTPException(503, "memory search is temporarily unavailable") from None
    except Exception:
        logger.exception(
            "admin_memory_search_failed", extra={"search_error_category": "search_unexpected_error"}
        )
        raise HTTPException(503, "memory search is temporarily unavailable") from None


def _search_unavailable_response(category: str) -> dict[str, object]:
    """Keep the Admin usable without exposing SQL/provider details to the browser."""
    action = (
        "Arama geçici olarak kullanılamıyor; migration ve veritabanı durumunu kontrol edin."
        if category == "search_migration_or_schema_error"
        else "Arama geçici olarak kullanılamıyor; daha sonra yeniden deneyin."
    )
    return SearchResponse(
        status="insufficient_sources",
        answer_tr=action,
        llm={"provider_calls": 0, "cache_hits": 0, "by_role": {}},
    ).model_dump(mode="json")


@router.post("/run-now")
async def run_now(request: Request) -> dict[str, object]:
    callback = getattr(request.app.state, "run_callback", None)
    try:
        result = callback() if callback else "completed_noop"
        if isawaitable(result):
            result = await result
    except Exception as error:
        result = {
            "status": "failed",
            "counts": {},
            "message": f"Runtime configuration failed: {type(error).__name__}",
        }
    request.app.state.last_run = (
        result
        if isinstance(result, str)
        else str(result.get("status", "completed"))
        if isinstance(result, Mapping)
        else "completed"
    )
    request.app.state.last_run_details = {
        "status": request.app.state.last_run,
        "at": datetime.now(UTC).isoformat(),
        "counts": result.get("counts", {}) if isinstance(result, Mapping) else {},
        "message": result.get("message", "Run callback completed.")
        if isinstance(result, Mapping)
        else "No ingestion job is connected to this deployment."
        if result == "completed_noop"
        else "Run callback completed.",
    }
    return request.app.state.last_run_details


@router.post("/youtube/blocked/{content_hash}/retry")
async def retry_blocked_youtube(content_hash: str, request: Request) -> dict[str, object]:
    """Allow one explicit, atomically claimed retry without exposing provider/source payloads."""
    if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
        raise HTTPException(422, "invalid blocked YouTube item")
    callback = getattr(request.app.state, "retry_blocked_youtube_callback", None)
    if not callable(callback):
        raise HTTPException(503, "blocked YouTube retry is unavailable in this deployment")
    try:
        result = await callback(content_hash)
    except Exception:
        raise HTTPException(500, "blocked YouTube retry could not be completed") from None
    if result.get("status") == "retry_not_available":
        raise HTTPException(409, "this blocked item is already being retried or no longer exists")
    return result


@router.post("/rss/blocked/{content_hash}/retry")
async def retry_blocked_rss(content_hash: str, request: Request) -> dict[str, object]:
    """Retry one atomically claimed RSS post-LLM block without exposing its source payload."""
    if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
        raise HTTPException(422, "invalid blocked RSS item")
    callback = getattr(request.app.state, "retry_blocked_rss_callback", None)
    if not callable(callback):
        raise HTTPException(503, "blocked RSS retry is unavailable in this deployment")
    try:
        result = await callback(content_hash)
    except Exception:
        raise HTTPException(500, "blocked RSS retry could not be completed") from None
    if result.get("status") == "retry_not_available":
        raise HTTPException(409, "this blocked item is already being retried or no longer exists")
    return result


@router.get("/config")
async def config(request: Request) -> dict[str, object]:
    return {
        "sources": {"items": await _admin_sources(request)},
        "models": _load_yaml(request.app.state.models_path),
        "interests": _load_yaml(request.app.state.interests_path),
    }


@router.get("", response_class=HTMLResponse)
async def page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context=await _dashboard_context(request),
    )


@router.get("/control-center", response_class=HTMLResponse)
async def control_center_page(request: Request) -> HTMLResponse:
    """Render the focused, source-only Control Center dashboard."""
    context = await _control_center_context(request)
    context.update({"page_title": "Dashboard", "active_page": "dashboard"})
    return templates.TemplateResponse(
        request=request,
        name="admin_control_center.html",
        context=context,
    )


@router.get("/control-center/briefings", response_class=HTMLResponse)
async def control_center_briefings_page(request: Request) -> HTMLResponse:
    """Render the read-only saved briefing history."""
    history = await _control_center_briefing_history(request)
    context = {
        "request": request,
        "history": history,
        "page_title": "Briefings",
        "active_page": "briefings",
    }
    return templates.TemplateResponse(
        request=request,
        name="admin_briefings.html",
        context=context,
        status_code=503 if history["error"] else 200,
    )


@router.get("/control-center/search", response_class=HTMLResponse)
async def control_center_search_page(request: Request) -> HTMLResponse:
    """Render the read-only Control Center memory search page."""
    return templates.TemplateResponse(
        request=request,
        name="admin_search.html",
        context={"request": request, "page_title": "Search / Memory", "active_page": "search"},
    )


@router.get("/control-center/scheduler", response_class=HTMLResponse)
async def control_center_scheduler_page(request: Request) -> HTMLResponse:
    """Render the persisted daily briefing schedule and safe runtime status."""
    context = await _control_center_scheduler_context(request)
    context.update({"page_title": "Scheduler", "active_page": "scheduler"})
    return templates.TemplateResponse(request=request, name="admin_scheduler.html", context=context)


@router.get("/control-center/search/{event_id}", response_class=HTMLResponse)
async def control_center_search_detail_page(event_id: str, request: Request) -> HTMLResponse:
    """Render one compact, persisted knowledge result."""
    if not event_id or len(event_id) > 128:
        raise HTTPException(422, "invalid event id")
    result = await _control_center_search_event(request, event_id)
    if result["error"]:
        return templates.TemplateResponse(
            request=request,
            name="admin_search_detail.html",
            context={
                "request": request,
                "event": None,
                "unavailable": True,
                "page_title": "Memory result",
                "active_page": "search",
            },
            status_code=503,
        )
    if result["item"] is None:
        raise HTTPException(404, "memory result not found")
    return templates.TemplateResponse(
        request=request,
        name="admin_search_detail.html",
        context={
            "request": request,
            "event": result["item"],
            "unavailable": False,
            "page_title": "Memory result",
            "active_page": "search",
        },
    )


@router.get("/control-center/briefings/{briefing_id}", response_class=HTMLResponse)
async def control_center_briefing_detail_page(
    briefing_id: str, request: Request
) -> HTMLResponse:
    """Render one saved briefing's complete persisted generated content."""
    result = await _control_center_briefing(request, briefing_id)
    if result["error"]:
        return templates.TemplateResponse(
            request=request,
            name="admin_briefing_detail.html",
            context={
                "request": request,
                "briefing": None,
                "unavailable": True,
                "page_title": "Briefing",
                "active_page": "briefings",
            },
            status_code=503,
        )
    if result["item"] is None:
        raise HTTPException(404, "briefing not found")
    return templates.TemplateResponse(
        request=request,
        name="admin_briefing_detail.html",
        context={
            "request": request,
            "briefing": result["item"],
            "unavailable": False,
            "page_title": "Briefing",
            "active_page": "briefings",
        },
    )


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request) -> HTMLResponse:
    """Render optional, browser-resumable first-run guidance."""
    context = await _control_center_context(request)
    context.update({"page_title": "Setup", "active_page": "onboarding"})
    return templates.TemplateResponse(
        request=request, name="admin_onboarding.html", context=context
    )


@router.post("/onboarding/scheduler")
async def save_onboarding_scheduler(
    preference: SchedulerPreference, request: Request
) -> dict[str, object]:
    repository = getattr(request.app.state, "onboarding_repository", None)
    scheduler = getattr(request.app.state, "scheduler", None)
    if repository is None or scheduler is None:
        raise HTTPException(503, "scheduler preferences are unavailable")
    if scheduler.state.running:
        raise HTTPException(409, "scheduler is currently running; retry shortly")
    try:
        await repository.save_scheduler_preference(preference)
        await scheduler.configure(preference.enabled, preference.daily_time)
    except Exception:
        raise HTTPException(503, "scheduler preferences are unavailable") from None
    return {"enabled": scheduler.state.enabled, "daily_time": scheduler.state.daily_time}


@router.get("/sources/ui", response_class=HTMLResponse)
async def sources_page(request: Request) -> HTMLResponse:
    """Render the database-backed source-management Control Center page."""
    context = await _control_center_context(request)
    context.update({"page_title": "Sources", "active_page": "sources"})
    return templates.TemplateResponse(request=request, name="admin_sources.html", context=context)


@router.get("/interests")
async def interests(request: Request) -> dict[str, object]:
    return _load_yaml(request.app.state.interests_path)


@router.post("/interests/{subject}/{direction}")
async def override(subject: str, direction: str, request: Request) -> dict[str, object]:
    if direction not in {"more", "less"} or not subject.replace("-", "").isalnum():
        raise HTTPException(status_code=422, detail="invalid subject or direction")
    path = request.app.state.interests_path
    data = _load_yaml(path)
    data.setdefault("admin_overrides", {})[subject] = 1 if direction == "more" else -1
    _save_yaml(path, data)
    return {"subject": subject, "delta": data["admin_overrides"][subject]}


@router.get("/sources")
async def sources(request: Request) -> dict[str, object]:
    return {"items": await _admin_sources(request)}


def _export_response(content: str, *, filename: str, media_type: str) -> PlainTextResponse:
    return PlainTextResponse(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _export(request: Request, format_name: str) -> str:
    service = SourceExportService(_source_repository(request))
    try:
        if format_name == "source-pack":
            return await service.source_pack_yaml()
        if format_name == "opml":
            return await service.opml()
        return await service.csv()
    except SourceExportRepositoryUnavailable:
        raise HTTPException(503, "managed source repository is unavailable") from None


@router.get("/source-packs/export")
async def export_source_pack(request: Request) -> PlainTextResponse:
    return _export_response(
        await _export(request, "source-pack"),
        filename="managed-sources.yaml",
        media_type="application/x-yaml",
    )


@router.get("/opml/export")
async def export_opml(request: Request) -> PlainTextResponse:
    return _export_response(
        await _export(request, "opml"),
        filename="managed-rss-sources.opml",
        media_type="application/xml",
    )


@router.get("/csv/export")
async def export_csv(request: Request) -> PlainTextResponse:
    return _export_response(
        await _export(request, "csv"), filename="managed-sources.csv", media_type="text/csv"
    )


@router.post("/source-packs/preview")
async def preview_source_pack(
    upload: SourcePackUpload, request: Request
) -> dict[str, object]:
    try:
        return await SourcePackService(_source_repository(request)).preview(upload.yaml)
    except Exception as error:
        _raise_source_pack_http_error(error)
        raise AssertionError("unreachable") from error


@router.post("/source-packs/import")
async def import_source_pack(
    upload: SourcePackUpload, request: Request
) -> dict[str, object]:
    try:
        result = await SourcePackService(_source_repository(request)).import_pack(upload.yaml)
    except Exception as error:
        _raise_source_pack_http_error(error)
        raise AssertionError("unreachable") from error
    await _queue_imported_category_questions(request, result)
    return result


@router.post("/opml/preview")
async def preview_opml(upload: OpmlUpload, request: Request) -> dict[str, object]:
    try:
        return await OpmlService(_source_repository(request)).preview(upload.opml)
    except Exception as error:
        _raise_opml_http_error(error)
        raise AssertionError("unreachable") from error


@router.post("/opml/import")
async def import_opml(upload: OpmlUpload, request: Request) -> dict[str, object]:
    try:
        result = await OpmlService(_source_repository(request)).import_opml(upload.opml)
    except Exception as error:
        _raise_opml_http_error(error)
        raise AssertionError("unreachable") from error
    await _queue_imported_category_questions(request, result)
    return result


@router.post("/csv/preview")
async def preview_csv(upload: CsvUpload, request: Request) -> dict[str, object]:
    try:
        return await CsvImportService(_source_repository(request)).preview(upload.csv)
    except Exception as error:
        _raise_delimited_import_http_error(error)
        raise AssertionError("unreachable") from error


@router.post("/csv/import")
async def import_csv(upload: CsvUpload, request: Request) -> dict[str, object]:
    try:
        result = await CsvImportService(_source_repository(request)).import_csv(upload.csv)
    except Exception as error:
        _raise_delimited_import_http_error(error)
        raise AssertionError("unreachable") from error
    await _queue_imported_category_questions(request, result)
    return result


@router.post("/bulk-urls/preview")
async def preview_bulk_urls(upload: BulkUrlUpload, request: Request) -> dict[str, object]:
    try:
        return await BulkUrlService(_source_repository(request)).preview(upload.urls)
    except Exception as error:
        _raise_delimited_import_http_error(error)
        raise AssertionError("unreachable") from error


@router.post("/bulk-urls/import")
async def import_bulk_urls(upload: BulkUrlUpload, request: Request) -> dict[str, object]:
    try:
        result = await BulkUrlService(_source_repository(request)).import_urls(upload.urls)
    except Exception as error:
        _raise_delimited_import_http_error(error)
        raise AssertionError("unreachable") from error
    await _queue_imported_category_questions(request, result)
    return result


@router.get("/sources/{source_id}")
async def get_source(source_id: str, request: Request) -> dict[str, object]:
    row = await _source_repository(request).get(source_id)
    if row is None:
        raise HTTPException(404, "managed source not found")
    return _source_view(row)


@router.post("/sources", status_code=201)
async def create_source(
    source: ManagedSourceCreate, request: Request
) -> dict[str, object]:
    try:
        row = await _source_repository(request).create(source)
    except Exception as error:
        _raise_source_http_error(error)
        raise AssertionError("unreachable") from error
    await _queue_imported_category_questions(
        request,
        {
            "sources": [
                {
                    "status": "created",
                    "source": {"category": row.get("category")},
                    "source_id": str(row["id"]),
                }
            ]
        },
    )
    return _source_view(row)


@router.patch("/sources/{source_id}")
async def update_source(
    source_id: str, update: ManagedSourceUpdate, request: Request
) -> dict[str, object]:
    try:
        row = await _source_repository(request).update(source_id, update)
    except Exception as error:
        _raise_source_http_error(error)
        raise AssertionError("unreachable") from error
    return _source_view(row)


@router.post("/sources/{source_id}/{enabled}")
async def toggle_source(source_id: str, enabled: bool, request: Request) -> dict[str, object]:
    changed = await _source_repository(request).set_enabled(source_id, enabled)
    if not changed:
        raise HTTPException(404, "managed source not found")
    return {"source_id": source_id, "enabled": enabled}


@router.delete("/sources/{source_id}")
async def remove_source(source_id: str, request: Request) -> dict[str, str]:
    try:
        await _source_repository(request).delete(source_id)
    except Exception as error:
        _raise_source_http_error(error)
    return {"status": "deleted"}


@router.post("/ui/sources")
async def add_source(source: ManagedSourceCreate, request: Request) -> dict[str, object]:
    created = await create_source(source, request)
    return {"source_id": created["id"], "enabled": created["enabled"]}


@router.delete("/ui/sources/{source_id}")
async def delete_source(source_id: str, request: Request) -> dict[str, str]:
    return await remove_source(source_id, request)


@router.post("/ui/sources/{source_id}/language")
async def update_youtube_language(
    source_id: str, update: YouTubeLanguageUpdate, request: Request
) -> dict[str, str | None]:
    try:
        await _source_repository(request).update(
            source_id, ManagedSourceUpdate(language=update.language)
        )
    except Exception as error:
        _raise_source_http_error(error)
    return {"source_id": source_id, "language": update.language}


@router.post("/ui/models")
async def update_model(update: ModelUpdate, request: Request) -> dict[str, str]:
    if update.role not in MODEL_ROLES:
        raise HTTPException(422, "unknown model role")
    data = _load_yaml(request.app.state.models_path)
    role = data.setdefault("roles", {}).setdefault(update.role, {})
    role["model"] = update.model
    _save_yaml(request.app.state.models_path, data)
    return {"role": update.role, "model": update.model}


@router.post("/gmail/connect")
async def gmail_connect(request: Request) -> RedirectResponse:
    oauth = getattr(request.app.state, "gmail_oauth", None)
    if (
        oauth is None
        or not oauth.configured
        or not getattr(request.app.state, "gmail_enabled", False)
        or not getattr(request.app.state, "gmail_encryption_ready", False)
    ):
        raise HTTPException(503, "Gmail OAuth token storage is not configured")
    try:
        return RedirectResponse(oauth.authorization_url(), status_code=302)
    except ValueError as error:
        raise HTTPException(
            429, "Too many active Gmail connection attempts; retry shortly"
        ) from error


@router.get("/gmail/callback", response_class=HTMLResponse)
async def gmail_callback(
    request: Request,
    code: str | None = Query(default=None, max_length=4096),
    state: str = Query(min_length=1, max_length=512),
    error: str | None = Query(default=None, max_length=64),
) -> HTMLResponse:
    oauth = getattr(request.app.state, "gmail_oauth", None)
    store = getattr(request.app.state, "store_gmail_token", None)
    if oauth is None or store is None:
        raise HTTPException(503, "Gmail OAuth is not configured")
    claim_telegram = getattr(request.app.state, "claim_telegram_gmail_oauth", None)
    finish_telegram = getattr(request.app.state, "finish_telegram_gmail_oauth", None)
    claimed = await _claim_telegram_gmail(claim_telegram, state)
    if claimed is not None and claimed != "active":
        return _telegram_gmail_result_response(claimed)
    is_telegram_link = claimed == "active"
    if error or not code:
        if is_telegram_link:
            result = await _finish_telegram_gmail(finish_telegram, state, None)
            return _telegram_gmail_result_response(result or "failed")
        return _oauth_failure_response("oauth_state_invalid_or_expired")
    try:
        token = await oauth.exchange(code, state)
    except OAuthFlowError as failure:
        if is_telegram_link:
            result = await _finish_telegram_gmail(finish_telegram, state, None)
            return _telegram_gmail_result_response(result or "failed")
        return _oauth_failure_response(failure.category)
    if is_telegram_link:
        result = await _finish_telegram_gmail(
            finish_telegram, state, token["refresh_token"]
        )
        return _telegram_gmail_result_response(result or "failed")
    try:
        await store(token["refresh_token"])
    except Exception:
        return _oauth_failure_response("token_storage_error")
    return HTMLResponse("<p>Gmail account connected. Return to <a href='/admin'>Admin</a>.</p>")


async def _finish_telegram_gmail(
    finish: object, state: str, refresh_token: str | None
) -> str | None:
    if not callable(finish):
        return None
    try:
        result = await finish(state, refresh_token)
    except Exception:
        logger.warning("gmail_telegram_link_failed", extra={"diagnostic_category": "link_finish"})
        return "failed"
    return result if isinstance(result, str) else None


async def _claim_telegram_gmail(claim: object, state: str) -> str | None:
    if not callable(claim):
        return None
    try:
        result = await claim(state)
    except Exception:
        logger.warning("gmail_telegram_link_failed", extra={"diagnostic_category": "claim"})
        return "failed"
    return result if isinstance(result, str) else None


def _telegram_gmail_result_response(result: str) -> HTMLResponse:
    if result == "connected":
        return HTMLResponse(
            "<h1>Gmail bağlantısı tamamlandı</h1><p>Telegram'a dönebilirsiniz.</p>"
        )
    return HTMLResponse(
        "<h1>Gmail bağlantısı tamamlanamadı</h1>"
        "<p>Telegram'dan /gmail komutuyla yeni bir bağlantı başlatın.</p>",
        status_code=400,
    )


@router.get("/briefings/{briefing_id}", response_class=HTMLResponse)
async def briefing_detail(briefing_id: str, request: Request) -> HTMLResponse:
    """Render persisted, bounded briefing data; viewing never invokes a model."""
    engine = getattr(request.app.state, "engine", None)
    rendered = None
    sections: dict[str, list[BriefingViewItem]] | None = None
    if engine is not None:
        try:
            async with engine.connect() as connection:
                rendered = (
                    await connection.execute(
                        text("SELECT rendered FROM briefings WHERE id = :id"), {"id": briefing_id}
                    )
                ).scalar_one_or_none()
                if rendered is not None:
                    sections = await _load_briefing_sections(connection, briefing_id)
        except Exception:
            logger.warning("briefing_detail_read_failed")
    if rendered is None:
        raise HTTPException(404, "briefing not found")
    if not sections or not any(sections.values()):
        sections = legacy_sections(str(rendered))
    return templates.TemplateResponse(
        request=request,
        name="briefing.html",
        context={
            "briefing_id": briefing_id,
            "sections": sections,
            "section_order": BRIEFING_SECTIONS,
            "legacy": not any(item.event_id for items in sections.values() for item in items),
        },
    )


async def _load_briefing_sections(
    connection: Any, briefing_id: str
) -> dict[str, list[BriefingViewItem]]:
    """Join only briefed event provenance and compact claims, never raw source/email payloads."""
    rows = (
        (
            await connection.execute(
                text(
                    "SELECT bi.event_id, bi.section, e.canonical_title, e.occurred_at, "
                    "bc.title AS briefing_title, bc.summary_tr, bc.what_changed_tr, "
                    "bc.why_important_tr, "
                    "coalesce(m.entities_json, '[]') AS entities_json, "
                    "ARRAY(SELECT c.statement FROM claims c WHERE c.event_id = bi.event_id "
                    "ORDER BY c.id LIMIT 2) AS facts, "
                    "ARRAY(SELECT i.inference_text FROM inferences i "
                    "WHERE i.event_id = bi.event_id "
                    "ORDER BY i.id LIMIT 2) AS inferences, "
                    "ARRAY(SELECT es.canonical_url FROM event_sources es "
                    "WHERE es.event_id = bi.event_id AND es.canonical_url IS NOT NULL "
                    "ORDER BY es.canonical_url LIMIT 3) AS source_links, "
                    "ARRAY(SELECT DISTINCT es.source_kind FROM event_sources es "
                    "WHERE es.event_id = bi.event_id AND es.source_kind IS NOT NULL) "
                    "AS source_kinds "
                    "FROM briefing_items bi LEFT JOIN events e ON e.id = bi.event_id "
                    "LEFT JOIN briefing_item_content bc ON bc.briefing_id = bi.briefing_id "
                    "AND bc.event_id = bi.event_id "
                    "LEFT JOIN event_search_metadata m ON m.event_id = bi.event_id "
                    "WHERE bi.briefing_id = :briefing_id ORDER BY bi.section, e.occurred_at DESC"
                ),
                {"briefing_id": briefing_id},
            )
        )
        .mappings()
        .all()
    )
    sections = {section: [] for section in BRIEFING_SECTIONS}
    subjects = {
        subject or str(row.get("canonical_title") or "")
        for row in rows
        for subject in (_json_strings(row.get("entities_json"))[:1] or [None])
        if subject
    }
    profiles = await _interest_profiles(connection, subjects)
    for row in rows:
        section = _display_section(str(row.get("section") or ""))
        if section is None or not row.get("canonical_title"):
            continue
        entities = _json_strings(row.get("entities_json"))
        subject = (
            entities[0]
            if entities
            else str(row["canonical_title"])
            if row.get("canonical_title")
            else None
        )
        explicit, adaptive = profiles.get(subject.casefold(), (0.0, 0.0)) if subject else (0.0, 0.0)
        facts = [str(value)[:520] for value in (row.get("facts") or []) if value]
        summary_tr = row.get("summary_tr")
        what_changed_tr = row.get("what_changed_tr")
        why_important_tr = row.get("why_important_tr")
        sections[section].append(
            BriefingViewItem(
                event_id=str(row["event_id"]),
                section=section,
                title=str(row.get("briefing_title") or row["canonical_title"])[:512],
                summary=compact_sentences(
                    str(summary_tr)
                    if summary_tr
                    else " ".join(facts) or str(row["canonical_title"])
                ),
                what_changed=(
                    compact_sentences(str(what_changed_tr), limit=1)
                    if what_changed_tr
                    else None
                ),
                why_important=(
                    compact_sentences(str(why_important_tr), limit=2)
                    if why_important_tr
                    else None
                ),
                verified_facts=facts,
                model_inferences=[
                    str(value)[:520] for value in (row.get("inferences") or []) if value
                ],
                source_links=safe_links(list(row.get("source_links") or [])),
                source_type=_source_type(row.get("source_kinds")),
                published_at=format_istanbul(row.get("occurred_at")),
                shown_because=shown_because(section, subject, explicit, adaptive),
                feedback_subject=subject,
                feedback_action=(
                    "more" if explicit > 0 and section != "Dünyada Neler Oldu? / World in Brief"
                    else (
                        "less"
                        if explicit < 0
                        and section != "Dünyada Neler Oldu? / World in Brief"
                        else None
                    )
                ),
                original_text=not bool(summary_tr),
            )
        )
    return sections


async def _interest_profiles(connection: Any, subjects: set[str]) -> dict[str, tuple[float, float]]:
    if not subjects:
        return {}
    rows = (
        (await connection.execute(text("SELECT subject, explicit, adaptive FROM interest_profile")))
        .mappings()
        .all()
    )
    wanted = {subject.casefold() for subject in subjects}
    return {
        str(row["subject"]).casefold(): (float(row["explicit"]), float(row["adaptive"]))
        for row in rows
        if str(row["subject"]).casefold() in wanted
    }


def _display_section(value: str) -> str | None:
    aliases = {
        "For You": "Senin İçin / For You",
        "World in Brief": "Dünyada Neler Oldu? / World in Brief",
    }
    normalized = aliases.get(value, value)
    return normalized if normalized in BRIEFING_SECTIONS else None


def _json_strings(value: object) -> list[str]:
    try:
        result = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return [str(item) for item in result] if isinstance(result, list) else []


def _source_type(values: object) -> str:
    kinds = [str(value) for value in values] if isinstance(values, list) else []
    return ", ".join(kinds[:2]) or "kaynak"


@router.post("/briefings/{briefing_id}/items/{event_id}/feedback")
async def briefing_feedback(
    briefing_id: str, event_id: str, feedback: BriefingFeedback, request: Request
) -> dict[str, object]:
    """Persist an explicit or light feedback signal without changing World ranking."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(503, "briefing feedback is unavailable in this deployment")
    try:
        async with engine.begin() as connection:
            result = await record_briefing_feedback(
                connection, briefing_id, event_id, feedback.action
            )
        return {
            "status": result.status,
            "selected_action": result.selected_action,
            "message": result.message,
        }
    except LookupError:
        raise HTTPException(404, "briefing item not found") from None
    except HTTPException:
        raise
    except Exception:
        logger.warning("briefing_feedback_write_failed")
        raise HTTPException(503, "briefing feedback could not be saved") from None
