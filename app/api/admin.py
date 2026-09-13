"""Local-only operational API plus a small server-rendered admin UI."""

import json
import logging
import re
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
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


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
                            "FROM scheduled_runs ORDER BY run_date DESC LIMIT 10"
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
        return await SourcePackService(_source_repository(request)).import_pack(upload.yaml)
    except Exception as error:
        _raise_source_pack_http_error(error)
        raise AssertionError("unreachable") from error


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
        return await OpmlService(_source_repository(request)).import_opml(upload.opml)
    except Exception as error:
        _raise_opml_http_error(error)
        raise AssertionError("unreachable") from error


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
        return await CsvImportService(_source_repository(request)).import_csv(upload.csv)
    except Exception as error:
        _raise_delimited_import_http_error(error)
        raise AssertionError("unreachable") from error


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
        return await BulkUrlService(_source_repository(request)).import_urls(upload.urls)
    except Exception as error:
        _raise_delimited_import_http_error(error)
        raise AssertionError("unreachable") from error


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
    code: str = Query(min_length=1, max_length=4096),
    state: str = Query(min_length=1, max_length=512),
) -> HTMLResponse:
    oauth = getattr(request.app.state, "gmail_oauth", None)
    store = getattr(request.app.state, "store_gmail_token", None)
    if oauth is None or store is None:
        raise HTTPException(503, "Gmail OAuth is not configured")
    try:
        token = await oauth.exchange(code, state)
    except OAuthFlowError as error:
        return _oauth_failure_response(error.category)
    try:
        await store(token["refresh_token"])
    except Exception:
        return _oauth_failure_response("token_storage_error")
    return HTMLResponse("<p>Gmail account connected. Return to <a href='/admin'>Admin</a>.</p>")


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
