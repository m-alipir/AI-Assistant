"""Small, atomic runtime source-catalog mutations shared by trusted control surfaces."""

import os
import re
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml

from app.config.sources import RssSourceConfig, SourceCatalog, YouTubeSourceConfig


class SourceControlError(ValueError):
    """A safe validation category for user-controlled source changes."""


def list_sources(path: Path) -> list[dict[str, str | bool]]:
    """Return compact non-secret source records suitable for Telegram or Admin rendering."""
    catalog = _load_catalog(path)
    rows: list[dict[str, str | bool]] = []
    for source in catalog.rss:
        rows.append(
            {
                "id": source_id("rss", source.name),
                "kind": "RSS",
                "name": source.name,
                "endpoint": source.url,
                "enabled": source.enabled,
            }
        )
    for source in catalog.youtube:
        rows.append(
            {
                "id": source_id("youtube", source.name),
                "kind": "YouTube",
                "name": source.name,
                "endpoint": source.channel_id,
                "enabled": source.enabled,
            }
        )
    return rows


def add_source(path: Path, kind: str, endpoint: str, name: str = "") -> dict[str, str]:
    """Add and enable one validated RSS or public YouTube channel source."""
    data = _load_data(path)
    normalized_kind = kind.casefold()
    if normalized_kind in {"", "auto"}:
        normalized_kind = "youtube" if _looks_like_youtube(endpoint) else "rss"
    if normalized_kind == "rss":
        url = _rss_url(endpoint)
        source_name = _source_name(name, urlparse(url).netloc)
        candidate = RssSourceConfig(name=source_name, url=url, stream="tech", enabled=True)
        entries = data.setdefault("rss", [])
        if any(isinstance(row, dict) and str(row.get("url", "")) == url for row in entries):
            raise SourceControlError("Bu RSS kaynağı zaten takip ediliyor.")
        entries.append(candidate.model_dump(mode="json"))
    elif normalized_kind == "youtube":
        channel_id = _youtube_channel_id(endpoint)
        source_name = _source_name(name, channel_id)
        candidate = YouTubeSourceConfig(
            name=source_name, channel_id=channel_id, stream="personalized", enabled=True
        )
        entries = data.setdefault("youtube", [])
        if any(
            isinstance(row, dict) and str(row.get("channel_id", "")) == channel_id
            for row in entries
        ):
            raise SourceControlError("Bu YouTube kanalı zaten takip ediliyor.")
        entries.append(candidate.model_dump(mode="json"))
    else:
        raise SourceControlError("Kaynak türü RSS veya YouTube olmalı.")
    _write_data(path, data)
    return {"id": source_id(normalized_kind, source_name), "name": source_name}


def disable_source(path: Path, requested_id: str) -> str:
    """Disable, rather than delete, a source to preserve its configuration history."""
    data = _load_data(path)
    for kind in ("rss", "youtube"):
        for entry in data.get(kind, []):
            if not isinstance(entry, dict):
                continue
            entry_id = source_id(kind, str(entry.get("name", "")))
            if entry_id == requested_id:
                entry["enabled"] = False
                _write_data(path, data)
                return str(entry.get("name", "Kaynak"))
    raise SourceControlError("Kaynak bulunamadı.")


def source_id(kind: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    if not slug:
        slug = f"source-{sha256(name.encode('utf-8')).hexdigest()[:8]}"
    return f"{kind}-{slug}"


def _load_catalog(path: Path) -> SourceCatalog:
    return SourceCatalog.model_validate(_load_data(path))


def _load_data(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise SourceControlError("Kaynak ayarları şu anda kullanılamıyor.") from error
    if not isinstance(data, dict):
        raise SourceControlError("Kaynak ayarları geçersiz.")
    return data


def _write_data(path: Path, data: dict[str, Any]) -> None:
    """Atomically replace the catalog so concurrent runtime reads never see partial YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            yaml.safe_dump(data, output, sort_keys=False, allow_unicode=True)
        os.replace(temporary_name, path)
    except OSError as error:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise SourceControlError("Kaynak ayarı kaydedilemedi.") from error


def _rss_url(value: str) -> str:
    candidate = value.strip()
    parsed = urlparse(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or len(candidate) > 2048
    ):
        raise SourceControlError("Geçerli bir RSS/Atom HTTP(S) adresi yazın.")
    return candidate


def _youtube_channel_id(value: str) -> str:
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"}:
        query_id = parse_qs(parsed.query).get("channel_id", [""])[0]
        path_parts = [part for part in parsed.path.split("/") if part]
        channel_path_id = ""
        if len(path_parts) == 2 and path_parts[0] == "channel":
            channel_path_id = path_parts[1]
        candidate = query_id or channel_path_id
    if not re.fullmatch(r"UC[\w-]{20,64}", candidate):
        raise SourceControlError("YouTube kanal kimliği `UC...` biçiminde olmalı.")
    return candidate


def _looks_like_youtube(value: str) -> bool:
    """Classify only explicit YouTube channel identifiers/URLs; all other URLs stay RSS."""
    candidate = value.strip()
    if re.fullmatch(r"UC[\w-]{20,64}", candidate):
        return True
    parsed = urlparse(candidate)
    host = parsed.hostname or ""
    return host.casefold() in {"youtube.com", "www.youtube.com", "m.youtube.com"}


def _source_name(value: str, fallback: str) -> str:
    candidate = value.strip() or fallback
    if not candidate or len(candidate) > 256:
        raise SourceControlError("Kaynak adı 1–256 karakter olmalı.")
    return candidate
