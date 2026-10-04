"""
Requirement 8.5: Approver bulk-approval file upload.

Deliberately mirrors field_mapping/manual_mapping.py's
parse_mapping_file()/apply_mapping_file() convention rather than
inventing a new one: explicit statements only, one per line, nothing
inferred, byte/line caps reused from that module rather than redefined
here, and every unparseable or invalid line is reported as an error
and skipped -- never guessed at.

Bugfix #6: an earlier version of this parser REQUIRED a status on every
line, while service.upload_approvals's docstring claimed a line could
omit its status and fall back to a caller-supplied default_status --
those two were inconsistent (the fallback code was unreachable dead
code, since the parser never actually produced a record with a missing
status). Status is now genuinely optional in the format below, so
`default_status` in service.upload_approvals is a real, reachable
behavior, not a claim the parser silently contradicted.

Line format (blank lines and '#' comments skipped):

    <break_id>: <STATUS>
    <break_id>: <STATUS> - <optional free-text note>
    <break_id>: - <optional free-text note>      (status omitted -> caller's default_status)
    <break_id>:                                   (status and note both omitted)

e.g.
    a1b2c3d4-...: RESOLVED - Confirmed FX timing difference
    e5f6a7b8-...: FALSE_POSITIVE
    9c8d7e6f-...: - Reviewed, using the batch default status
"""

from __future__ import annotations

import re

from field_mapping.manual_mapping import MAX_MAPPING_FILE_BYTES, MAX_MAPPING_FILE_LINES

#: STATUS, if present, is one or more uppercase letters/underscores --
#: which never starts with '-', so "- <note>" (status omitted) and
#: "STATUS - <note>" (status given) are never ambiguous.
_LINE_RE = re.compile(
    r"^\s*(?P<break_id>[^:]+?)\s*:\s*(?:(?P<status>[A-Z_]+)\s*)?(?:-\s*(?P<note>.*))?$"
)


class ApprovalFileError(Exception):
    """Raised when the file itself can't be processed at all (too large,
    too many lines) -- distinct from a single bad line, which is
    reported per-line in `errors` instead of raising."""


def parse_approval_file(content: str) -> tuple[list[dict], list[dict]]:
    if len(content.encode("utf-8", errors="ignore")) > MAX_MAPPING_FILE_BYTES:
        raise ApprovalFileError(f"Approval file exceeds the {MAX_MAPPING_FILE_BYTES} byte limit")

    lines = content.splitlines()
    if len(lines) > MAX_MAPPING_FILE_LINES:
        raise ApprovalFileError(f"Approval file exceeds {MAX_MAPPING_FILE_LINES} lines")

    records: list[dict] = []
    errors: list[dict] = []

    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        match = _LINE_RE.match(line)
        if not match:
            errors.append({
                "line_number": number, "line": line,
                "error": "expected '<break_id>: <STATUS>', '<break_id>: <STATUS> - <note>', "
                         "or '<break_id>: - <note>' (status omitted)",
            })
            continue

        break_id = match.group("break_id").strip()
        raw_status = match.group("status")
        status = raw_status.strip() if raw_status else None  # None -> caller's default_status
        note = (match.group("note") or "").strip() or None
        if not break_id:
            errors.append({"line_number": number, "line": line, "error": "break_id is empty"})
            continue

        records.append({"break_id": break_id, "status": status, "note": note, "line_number": number})

    return records, errors
