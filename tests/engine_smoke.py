"""Conversion smoke tests for automated conversion engine bumps."""

from __future__ import annotations

from omnivert.conversion import service
from omnivert.schemas import ConvertOptions


def assert_ok(name: str, content: str, extension: str) -> None:
    result = service.convert_text(content, extension, "utf-8", ConvertOptions())
    if not result.ok or not result.markdown:
        raise AssertionError(f"{name} conversion failed: {result.error}")


def main() -> None:
    assert_ok("plain text", "hello world", ".txt")
    assert_ok("csv", "name,value\nalpha,1\n", ".csv")
    assert_ok("html", "<html><body><h1>Hello</h1><p>World</p></body></html>", ".html")


if __name__ == "__main__":
    main()

