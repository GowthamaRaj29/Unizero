"""
Requirement 1, step 1: Ingestion.

One public entry point — ingest(source) — that figures out for itself
whether it's looking at a CSV, an Excel file, a JSON file, an XML file, or
a REST API, rather than the caller having to declare the type up front.
Detection order:

  1. URL scheme (http:// or https://)                     -> API
  2. File extension (.csv/.xlsx/.xls/.json/.xml)           -> matching format
  3. Content sniffing, if the extension didn't tell us anything:
       - zip signature (PK\\x03\\x04)         -> Excel (.xlsx is a zip)
       - OLE signature (D0 CF 11 E0...)       -> Excel (legacy .xls)
       - starts with '<'                      -> XML
       - starts with '{' or '['               -> JSON
       - otherwise, if it decodes as text     -> CSV

Whatever the source turns out to be, the result converges into the same
shape: an IngestResult holding a pandas DataFrame plus metadata. Nothing
downstream (validation, AI assessment) needs to know which kind of source
it came from, or how it was detected.
"""

from __future__ import annotations

import json
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import ParseError as ET_ParseError

import pandas as pd
import requests

logger = logging.getLogger("onerecon.ingestion.ingest")

_EXTENSION_MAP = {
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".json": "json",
    ".xml": "xml",
}
_JSON_LIST_KEYS = ("data", "records", "items", "results")

_ZIP_SIGNATURE = b"PK\x03\x04"          # .xlsx is a zip archive
_OLE_SIGNATURE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"  # legacy .xls


class IngestionError(Exception):
    """Raised for any failure reading a source, including failing to
    determine what kind of source it is — callers should catch this and
    surface it as a clean error, never let it crash the pipeline."""


@dataclass
class IngestResult:
    df: pd.DataFrame
    metadata: dict = field(default_factory=dict)


def _build_metadata(df: pd.DataFrame, source: str, source_type: str, extra: dict | None = None) -> dict:
    metadata = {
        "source": source,
        "source_type": source_type,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        metadata.update(extra)
    return metadata


def detect_format(source: str) -> str:
    """
    Returns "csv", "excel", "json", "xml", or "api" based on inspecting
    the source itself — never something the caller has to declare. Raises
    IngestionError if the source can't be found or its format can't be
    determined, so the pipeline fails cleanly rather than guessing wrong.
    """
    if source.startswith("http://") or source.startswith("https://"):
        return "api"

    path = Path(source)
    if not path.exists():
        raise IngestionError(f"Source not found and is not a URL: {source}")

    suffix = path.suffix.lower()
    if suffix in _EXTENSION_MAP:
        return _EXTENSION_MAP[suffix]

    # Extension didn't tell us — sniff the content instead.
    try:
        with open(path, "rb") as fh:
            header = fh.read(64)
    except OSError as exc:
        raise IngestionError(f"Could not read source to detect its format: {exc}") from exc

    if header.startswith(_ZIP_SIGNATURE) or header.startswith(_OLE_SIGNATURE):
        logger.info("detect_format: %s has no recognized extension, sniffed as excel", source)
        return "excel"

    try:
        decoded = header.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestionError(
            f"Could not determine format of {source}: not CSV, Excel, JSON, XML, or a URL"
        ) from exc

    stripped = decoded.lstrip()
    if stripped.startswith("<"):
        logger.info("detect_format: %s has no recognized extension, sniffed as xml", source)
        return "xml"
    if stripped.startswith(("{", "[")):
        logger.info("detect_format: %s has no recognized extension, sniffed as json", source)
        return "json"

    logger.info("detect_format: %s has no recognized extension, sniffed as csv (text content)", source)
    return "csv"


def _ingest_csv(path: str | Path) -> IngestResult:
    file_path = Path(path)
    start = time.monotonic()
    try:
        df = pd.read_csv(file_path)
    except (pd.errors.ParserError, UnicodeDecodeError, OSError) as exc:
        logger.error("Failed to parse CSV %s: %s", file_path, exc)
        raise IngestionError(f"Could not parse CSV file: {exc}") from exc

    elapsed = round(time.monotonic() - start, 3)
    metadata = _build_metadata(df, str(file_path), "csv", {"time_taken_seconds": elapsed})
    logger.info("Ingested CSV %s: %d rows, %d columns", file_path, len(df), len(df.columns))
    return IngestResult(df=df, metadata=metadata)


def _ingest_excel(path: str | Path, sheet_name: str | int = 0) -> IngestResult:
    file_path = Path(path)
    start = time.monotonic()
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except (ValueError, OSError) as exc:
        logger.error("Failed to parse Excel %s: %s", file_path, exc)
        raise IngestionError(f"Could not parse Excel file: {exc}") from exc

    elapsed = round(time.monotonic() - start, 3)
    metadata = _build_metadata(
        df, str(file_path), "excel", {"time_taken_seconds": elapsed, "sheet_name": sheet_name}
    )
    logger.info("Ingested Excel %s: %d rows, %d columns", file_path, len(df), len(df.columns))
    return IngestResult(df=df, metadata=metadata)


def _ingest_json(path: str | Path, data_key: str | None = None) -> IngestResult:
    """
    The root can be a plain list of records, or a dict wrapping the list
    under a key — data_key names that key explicitly; if not given, a few
    common conventions (data/records/items/results) are tried first.
    """
    file_path = Path(path)
    start = time.monotonic()
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        logger.error("Failed to parse JSON %s: %s", file_path, exc)
        raise IngestionError(f"Could not parse JSON file: {exc}") from exc

    records = _extract_records(payload, data_key, source_label=str(file_path))
    df = pd.DataFrame(records)
    elapsed = round(time.monotonic() - start, 3)
    metadata = _build_metadata(df, str(file_path), "json", {"time_taken_seconds": elapsed})
    logger.info("Ingested JSON %s: %d rows, %d columns", file_path, len(df), len(df.columns))
    return IngestResult(df=df, metadata=metadata)


def _extract_records(payload, data_key: str | None, source_label: str) -> list:
    """Pulls the record list out of a JSON payload that might be a bare
    list or a dict wrapping one under some key."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if data_key is not None:
            records = payload.get(data_key)
            if not isinstance(records, list):
                raise IngestionError(
                    f"Expected a list under {data_key!r} in {source_label}, got {type(records).__name__}"
                )
            return records
        for candidate_key in _JSON_LIST_KEYS:
            if isinstance(payload.get(candidate_key), list):
                return payload[candidate_key]
        raise IngestionError(
            f"Could not find a record list in {source_label} — tried keys {_JSON_LIST_KEYS}; "
            "pass data_key explicitly if it uses a different key"
        )
    raise IngestionError(f"Unsupported JSON root type in {source_label}: {type(payload).__name__}")


def _detect_xml_record_tag(path: Path) -> str | None:
    """Finds the tag that repeats most often as siblings anywhere in the
    tree — that's the record element, whatever it's called. Purely
    structural (which tag repeats), so it works for any XML shape."""
    from collections import Counter

    try:
        tree = ET.parse(path)
    except ET_ParseError as exc:
        raise IngestionError(f"Could not parse XML file: {exc}") from exc

    tag_counts: Counter = Counter()
    for parent in tree.getroot().iter():
        sibling_tags = Counter(child.tag for child in parent)
        for tag, count in sibling_tags.items():
            if count > 1:
                tag_counts[tag] += count

    if not tag_counts:
        return None
    return tag_counts.most_common(1)[0][0]


def _ingest_xml(path: str | Path, record_tag: str | None = None) -> IngestResult:
    """Uses pandas' XML reader with the built-in etree parser. If the
    caller names record_tag explicitly, that's used directly. Otherwise,
    both the default reading (root's direct children) and the
    structurally-detected repeating tag are tried, and whichever actually
    produced more rows wins — a shallow parse that "succeeds" with too
    few rows (e.g. matching a wrapper element instead of the real
    records) is not silently accepted just because it didn't error."""
    file_path = Path(path)
    start = time.monotonic()

    if record_tag:
        try:
            df = pd.read_xml(file_path, xpath=f".//{record_tag}", parser="etree")
        except (ValueError, ET_ParseError) as exc:
            raise IngestionError(f"Could not parse XML with tag {record_tag!r}: {exc}") from exc
    else:
        try:
            default_df = pd.read_xml(file_path, xpath="./*", parser="etree")
        except (ValueError, ET_ParseError) as exc:
            # A malformed file will fail identically on every subsequent
            # attempt too — fail fast here instead of limping into the
            # structural-detection fallback with a file that can't be parsed.
            raise IngestionError(f"Could not parse XML file: {exc}") from exc

        detected_tag = _detect_xml_record_tag(file_path)
        detected_df = pd.DataFrame()
        if detected_tag:
            try:
                detected_df = pd.read_xml(file_path, xpath=f".//{detected_tag}", parser="etree")
            except (ValueError, ET_ParseError):
                pass

        if len(detected_df) > len(default_df):
            logger.info(
                "_ingest_xml: structural detection (%r, %d rows) beat default parse (%d rows)",
                detected_tag, len(detected_df), len(default_df),
            )
            df = detected_df
        else:
            df = default_df

        if df.empty:
            raise IngestionError(f"Could not identify a record structure in {file_path}")

    elapsed = round(time.monotonic() - start, 3)
    metadata = _build_metadata(df, str(file_path), "xml", {"time_taken_seconds": elapsed})
    logger.info("Ingested XML %s: %d rows, %d columns", file_path, len(df), len(df.columns))
    return IngestResult(df=df, metadata=metadata)


def _ingest_api(
    url: str,
    page_param: str = "page",
    per_page_param: str = "per_page",
    per_page: int = 500,
    data_key: str = "data",
    total_pages_key: str = "total_pages",
    max_pages: int = 1000,
    timeout_seconds: int = 15,
) -> IngestResult:
    """
    Pulls every page of a paginated JSON REST API and concatenates the
    records. Parameter names are configurable because different APIs use
    different pagination conventions — this function makes no assumption
    about which API it's pointed at, only that `source` is its full URL.
    """
    all_records: list[dict] = []
    page = 1
    start = time.monotonic()

    while page <= max_pages:
        try:
            response = requests.get(
                url,
                params={page_param: page, per_page_param: per_page},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.error("API request failed for %s (page %d): %s", url, page, exc)
            raise IngestionError(f"API request failed: {exc}") from exc
        except ValueError as exc:
            logger.error("API returned non-JSON response from %s: %s", url, exc)
            raise IngestionError(f"API returned invalid JSON: {exc}") from exc

        records = _extract_records(payload, data_key, source_label=f"{url} (page {page})")
        all_records.extend(records)

        total_pages = payload.get(total_pages_key)
        if total_pages is not None and page >= total_pages:
            break
        if not records:  # no total_pages key given, stop when a page is empty
            break
        page += 1

    if page > max_pages:
        logger.warning("ingest hit max_pages=%d for %s — data may be incomplete", max_pages, url)

    df = pd.DataFrame(all_records)
    elapsed = round(time.monotonic() - start, 3)
    metadata = _build_metadata(df, url, "api", {"time_taken_seconds": elapsed, "pages_fetched": page})
    logger.info("Ingested API %s: %d rows across %d page(s)", url, len(df), page)
    return IngestResult(df=df, metadata=metadata)


def ingest(
    source: str,
    *,
    sheet_name: str | int = 0,
    json_data_key: str | None = None,
    xml_record_tag: str | None = None,
    page_param: str = "page",
    per_page_param: str = "per_page",
    per_page: int = 500,
    data_key: str = "data",
    total_pages_key: str = "total_pages",
    max_pages: int = 1000,
    timeout_seconds: int = 15,
) -> IngestResult:
    """
    The single ingestion entry point. `source` is a file path or a full
    URL — nothing else needs to be declared, including which format it
    is. Format-specific keyword arguments (sheet_name for Excel;
    json_data_key for JSON; xml_record_tag for XML, only needed if
    structural auto-detection guesses wrong; the rest for API pagination)
    are simply ignored if they don't apply to the detected format.
    """
    fmt = detect_format(source)
    if fmt == "csv":
        return _ingest_csv(source)
    if fmt == "excel":
        return _ingest_excel(source, sheet_name)
    if fmt == "json":
        return _ingest_json(source, json_data_key)
    if fmt == "xml":
        return _ingest_xml(source, xml_record_tag)
    if fmt == "api":
        return _ingest_api(
            source, page_param, per_page_param, per_page, data_key, total_pages_key, max_pages, timeout_seconds
        )
    raise IngestionError(f"Unsupported format detected for {source!r}: {fmt}")  # unreachable