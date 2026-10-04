import pytest

from break_management.approval_file import ApprovalFileError, parse_approval_file


def test_parses_status_and_note():
    content = "break-1: RESOLVED - Confirmed FX timing difference\nbreak-2: FALSE_POSITIVE"
    records, errors = parse_approval_file(content)

    assert errors == []
    assert records == [
        {"break_id": "break-1", "status": "RESOLVED", "note": "Confirmed FX timing difference", "line_number": 1},
        {"break_id": "break-2", "status": "FALSE_POSITIVE", "note": None, "line_number": 2},
    ]


def test_skips_blank_lines_and_comments():
    content = "\n# a comment\nbreak-1: RESOLVED\n\n"
    records, errors = parse_approval_file(content)
    assert len(records) == 1
    assert errors == []


def test_malformed_line_reported_as_error_not_guessed():
    content = "this line has no colon or status"
    records, errors = parse_approval_file(content)
    assert records == []
    assert len(errors) == 1
    assert errors[0]["line_number"] == 1


def test_empty_break_id_is_an_error():
    content = ": RESOLVED"
    records, errors = parse_approval_file(content)
    assert records == []
    assert len(errors) == 1


def test_oversized_file_raises():
    with pytest.raises(ApprovalFileError):
        parse_approval_file("x" * (2 * 1024 * 1024 + 1))
