"""Batch packaging: archive naming, size bounds, and the download header.

``content_disposition`` earned its own tests the hard way: Starlette encodes response headers
as latin-1, so a converted file whose name carries a smart quote or CJK would raise
UnicodeEncodeError and 500 the download.
"""

from __future__ import annotations

import io
import zipfile

from omnivert import jobs
from omnivert.schemas import ConversionResult


def _ok(filename: str, markdown: str = "# hello") -> ConversionResult:
    return ConversionResult(filename=filename, ok=True, markdown=markdown)


def _failed(filename: str) -> ConversionResult:
    return ConversionResult(filename=filename, ok=False, error="boom", error_kind="error")


def test_register_and_get_round_trip():
    batch_id = jobs.register([_ok("a.txt")])
    assert jobs.get(batch_id)[0].filename == "a.txt"


def test_get_unknown_batch_returns_none():
    assert jobs.get("does-not-exist") is None


def test_single_success_is_served_as_markdown_not_a_zip():
    results = [_ok("only.txt"), _failed("broken.pdf")]
    assert jobs.single_markdown(results) is not None


def test_multiple_successes_are_not_single_markdown():
    assert jobs.single_markdown([_ok("a.txt"), _ok("b.txt")]) is None


def test_blank_markdown_does_not_count_as_success():
    assert jobs.successful([_ok("empty.txt", "   ")]) == []


def test_zip_preserves_subfolders_and_swaps_the_extension():
    data = jobs.build_zip([_ok("docs/guide.docx"), _ok("docs/nested/spec.pdf")])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
    assert "docs/guide.md" in names
    assert "docs/nested/spec.md" in names
    assert "_conversion-report.txt" in names


def test_duplicate_names_are_deduplicated():
    data = jobs.build_zip([_ok("report.docx"), _ok("report.pdf")])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist() if n != "_conversion-report.txt"]
    assert sorted(names) == ["report-2.md", "report.md"]


def test_report_records_failures_so_nothing_is_silently_dropped():
    data = jobs.build_zip([_ok("good.txt"), _failed("bad.pdf")])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        report = zf.read("_conversion-report.txt").decode("utf-8")
    assert "bad.pdf" in report and "FAILED" in report
    assert "Succeeded: 1" in report and "Failed: 1" in report


def test_unsafe_filename_characters_are_stripped():
    data = jobs.build_zip([_ok('we:ird*na<me>.txt')])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist() if n != "_conversion-report.txt"]
    assert names == ["we_ird_na_me_.md"]
    assert not any(c in names[0] for c in ':*<>"|?')


def test_oversized_markdown_is_truncated_and_reported():
    huge = "x" * (jobs._MAX_MD_BYTES + 1024)
    data = jobs.build_zip([_ok("huge.txt", huge)])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        body = zf.read("huge.md").decode("utf-8")
        report = zf.read("_conversion-report.txt").decode("utf-8")
    assert len(body.encode("utf-8")) <= jobs._MAX_MD_BYTES + 200
    assert "truncated" in body and "truncated" in report


# --- Content-Disposition --------------------------------------------------------------

def test_content_disposition_is_latin1_encodable_for_unicode_names():
    header = jobs.content_disposition("café—報告.md")
    header.encode("latin-1")  # would raise before the RFC 5987 handling


def test_content_disposition_carries_both_forms():
    header = jobs.content_disposition("plain.md")
    assert 'filename="plain.md"' in header
    assert "filename*=UTF-8''plain.md" in header


def test_content_disposition_never_yields_an_empty_ascii_name():
    header = jobs.content_disposition("報告.md")
    assert 'filename=""' not in header
    assert "filename*=UTF-8''" in header


def test_content_disposition_escapes_quotes():
    header = jobs.content_disposition('we"ird.md')
    # A stray quote would terminate the quoted-string and let the rest be reinterpreted.
    assert header.count('"') == 2


def test_lru_cap_evicts_oldest_batches():
    ids = [jobs.register([_ok(f"{i}.txt")]) for i in range(jobs._MAX_BATCHES + 5)]
    assert jobs.get(ids[0]) is None, "oldest batch should have been evicted"
    assert jobs.get(ids[-1]) is not None


# --- header injection -----------------------------------------------------------------

def test_crlf_in_a_document_title_cannot_reach_the_response_header():
    """A converted document's <title> becomes the download filename.

    HTML titles come from whatever was converted rather than from the user, and a raw CRLF
    in one was landing verbatim in the Content-Disposition header uvicorn writes out.
    """
    header = jobs.content_disposition(jobs._md_arcname("rep\r\nX-Injected: yes"))
    assert "\r" not in header
    assert "\n" not in header


def test_content_disposition_strips_controls_itself():
    """Not every caller goes through _md_arcname, so the header builder defends itself."""
    header = jobs.content_disposition("a\r\nb\tc\x00d.md")
    for bad in ("\r", "\n", "\t", "\x00"):
        assert bad not in header
    header.encode("latin-1")


def test_control_characters_are_stripped_from_archive_names():
    data = jobs.build_zip([_ok("we\r\nird.txt")])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist() if n != "_conversion-report.txt"]
    assert names and all("\r" not in n and "\n" not in n for n in names)
