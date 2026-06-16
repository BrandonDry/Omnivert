"""Report what this conversion engine can actually do: version, optional dependencies,
ffmpeg availability, YouTube extra availability, and the supported-format table."""

from __future__ import annotations

import importlib.util
import platform
import shutil
from importlib.metadata import PackageNotFoundError, version
from typing import List

from .schemas import CapabilitiesResponse, DependencyInfo, FormatInfo

# Optional dependencies that gate specific converters, with a friendly label.
_OPTIONAL_DEPS = [
    ("pdfminer.six", "pdfminer", "PDF"),
    ("pdfplumber", "pdfplumber", "PDF (tables/layout)"),
    ("mammoth", "mammoth", "Word .docx"),
    ("python-pptx", "pptx", "PowerPoint .pptx"),
    ("openpyxl", "openpyxl", "Excel .xlsx"),
    ("xlrd", "xlrd", "Excel .xls"),
    ("magika", "magika", "content-based type detection"),
    ("Pillow", "PIL", "images"),
    ("pydub", "pydub", "audio decoding"),
    ("SpeechRecognition", "speech_recognition", "audio transcription"),
    ("azure-ai-documentintelligence", "azure.ai.documentintelligence", "Azure Document Intelligence"),
    ("azure-ai-contentunderstanding", "azure.ai.contentunderstanding", "Azure Content Understanding"),
    ("openai", "openai", "LLM image captioning"),
    ("youtube-transcript-api", "youtube_transcript_api", "YouTube transcription"),
]

# Curated supported-format table (built-in converters).
_FORMATS = [
    FormatInfo(label="PDF", extensions=[".pdf"]),
    FormatInfo(label="Word", extensions=[".docx"]),
    FormatInfo(label="PowerPoint", extensions=[".pptx"]),
    FormatInfo(label="Excel", extensions=[".xlsx", ".xls"]),
    FormatInfo(label="Images", extensions=[".jpg", ".jpeg", ".png"], note="EXIF/OCR; Claude captions optional"),
    FormatInfo(label="Audio", extensions=[".wav", ".mp3", ".m4a", ".mp4"], note="Non-WAV needs ffmpeg"),
    FormatInfo(label="HTML", extensions=[".html", ".htm"]),
    FormatInfo(label="CSV", extensions=[".csv"]),
    FormatInfo(label="JSON", extensions=[".json"]),
    FormatInfo(label="XML / RSS", extensions=[".xml", ".rss"]),
    FormatInfo(label="EPUB", extensions=[".epub"]),
    FormatInfo(label="Outlook message", extensions=[".msg"]),
    FormatInfo(label="Jupyter notebook", extensions=[".ipynb"]),
    FormatInfo(label="ZIP archive", extensions=[".zip"], note="Recursively converts contents"),
    FormatInfo(label="Plain text", extensions=[".txt", ".md"]),
    FormatInfo(label="URLs", extensions=["http://", "https://"], note="Webpages, Wikipedia, Bing, YouTube pages"),
]


def _is_importable(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def _safe_version(dist_name: str) -> str | None:
    try:
        return version(dist_name)
    except PackageNotFoundError:
        return None


def get_capabilities() -> CapabilitiesResponse:
    deps: List[DependencyInfo] = []
    youtube_available = False
    for dist_name, module_name, _label in _OPTIONAL_DEPS:
        installed = _is_importable(module_name)
        if dist_name == "youtube-transcript-api":
            youtube_available = installed
        deps.append(
            DependencyInfo(name=dist_name, installed=installed, version=_safe_version(dist_name))
        )

    return CapabilitiesResponse(
        engine_version=_safe_version("markitdown"),
        python_version=platform.python_version(),
        ffmpeg_available=shutil.which("ffmpeg") is not None,
        youtube_available=youtube_available,
        dependencies=deps,
        formats=_FORMATS,
    )
