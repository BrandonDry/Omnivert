"""Report what this conversion engine can actually do: version, optional dependencies,
ffmpeg availability, and the supported-format table.

The format table and the dependency list are both derived from the engine version pinned in
``pyproject.toml`` (markitdown 0.1.7). Two rules keep this honest:

1. Every extension listed here is one the pinned engine's converters actually accept. The
   lists were read off the converters' ``ACCEPTED_FILE_EXTENSIONS``, not from memory. An
   earlier version of this table under-reported ``.markdown``, ``.text``, ``.jsonl`` and
   ``.atom``, and advertised YouTube support that the pin cannot deliver.
2. Every dependency listed here is one our pin actually installs, so anything reported
   ``missing`` is a genuinely broken install rather than a normal state.

   Note the limit of that check: ``_is_importable`` uses ``importlib.util.find_spec``, which
   locates a module without importing it. It therefore catches a dependency that is absent,
   but NOT one that is present and broken. The cloud-sync dehydration failure in CLAUDE.md's
   environment caveat is the second kind, so this dialog will still report such an install as
   healthy and the conversion will fail later. Detecting that would mean actually importing
   pandas, the Azure SDKs and onnxruntime on every capabilities call, which is seconds of
   startup cost for a rare failure; the trade is deliberate.

``_OPTIONAL_DEPS`` must stay in sync with the ``copy_metadata`` list in
``packaging/app.spec``, or the frozen build reports ``None`` for every version.
``tests/test_capabilities.py`` enforces that; do not rely on remembering it.
"""

from __future__ import annotations

import importlib.util
import platform
import shutil
from importlib.metadata import PackageNotFoundError, version
from typing import List

from .schemas import CapabilitiesResponse, DependencyInfo, FormatInfo

# (distribution name, importable module, which converter it gates). Every entry is pulled in
# by the curated extras pinned in pyproject.toml, plus openai, which is our own direct
# dependency for Claude captioning (markitdown does not pull it in under any extra).
_OPTIONAL_DEPS = [
    ("pdfminer.six", "pdfminer", "PDF"),
    ("pdfplumber", "pdfplumber", "PDF (tables/layout)"),
    ("mammoth", "mammoth", "Word .docx"),
    # lxml gates two converters, and neither is obvious. markitdown never imports it: the
    # .docx path reaches it through BeautifulSoup(features="xml") in
    # converter_utils/docx/pre_process.py, a feature bs4 can only serve via lxml. It is
    # also a hard requirement of python-pptx, along with Pillow.
    ("lxml", "lxml", "Word .docx and PowerPoint .pptx"),
    ("python-pptx", "pptx", "PowerPoint .pptx"),
    ("Pillow", "PIL", "PowerPoint .pptx images"),
    ("openpyxl", "openpyxl", "Excel .xlsx"),
    ("xlrd", "xlrd", "Excel .xls"),
    ("pandas", "pandas", "Excel tables"),
    ("olefile", "olefile", "Outlook .msg"),
    ("pydub", "pydub", "audio decoding"),
    ("SpeechRecognition", "speech_recognition", "audio transcription"),
    ("azure-ai-documentintelligence", "azure.ai.documentintelligence", "Azure Document Intelligence"),
    ("azure-ai-contentunderstanding", "azure.ai.contentunderstanding", "Azure Content Understanding"),
    ("azure-identity", "azure.identity", "Azure authentication"),
    ("openai", "openai", "Claude image captioning"),
    ("magika", "magika", "content-based type detection"),
]

# Supported formats, with the distributions that gate each one. ``requires`` names entries in
# _OPTIONAL_DEPS; an empty list means the engine's core dependencies already cover it.
_FORMAT_SPECS = [
    ("PDF", [".pdf"], ["pdfminer.six", "pdfplumber"], None),
    ("Word", [".docx"], ["mammoth", "lxml"], None),
    ("PowerPoint", [".pptx"], ["python-pptx", "lxml", "Pillow"], None),
    ("Excel", [".xlsx"], ["openpyxl", "pandas"], None),
    ("Excel 97-2003", [".xls"], ["xlrd", "pandas"], None),
    ("Outlook message", [".msg"], ["olefile"], None),
    ("Audio", [".wav", ".mp3", ".m4a", ".mp4"], ["pydub", "SpeechRecognition"],
     "Transcription; anything but .wav also needs ffmpeg"),
    ("Images", [".jpg", ".jpeg", ".png"], [],
     "EXIF metadata via exiftool; Claude captions optional"),
    ("HTML", [".html", ".htm"], [], None),
    ("CSV", [".csv"], [], None),
    ("JSON", [".json", ".jsonl"], [], None),
    ("XML / RSS / Atom", [".xml", ".rss", ".atom"], [], None),
    ("EPUB", [".epub"], [], None),
    ("Jupyter notebook", [".ipynb"], [], None),
    ("ZIP archive", [".zip"], [], "Recursively converts contents"),
    ("Plain text", [".txt", ".text", ".md", ".markdown"], [], None),
    ("URLs", ["http://", "https://"], [], "Webpages, Wikipedia, and Bing results pages"),
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
    installed: dict[str, bool] = {}
    for dist_name, module_name, gates in _OPTIONAL_DEPS:
        present = _is_importable(module_name)
        installed[dist_name] = present
        deps.append(
            DependencyInfo(
                name=dist_name,
                installed=present,
                version=_safe_version(dist_name),
                gates=gates,
            )
        )

    ffmpeg = shutil.which("ffmpeg") is not None

    formats: List[FormatInfo] = []
    for label, extensions, requires, note in _FORMAT_SPECS:
        # A format is usable when every distribution gating it imports. Audio is the one
        # case with a non-Python gate too: only .wav decodes without ffmpeg on the PATH.
        available = all(installed.get(dist, False) for dist in requires)
        formats.append(
            FormatInfo(
                label=label,
                extensions=extensions,
                note=note,
                requires=requires,
                available=available,
            )
        )

    return CapabilitiesResponse(
        engine_version=_safe_version("markitdown"),
        python_version=platform.python_version(),
        ffmpeg_available=ffmpeg,
        dependencies=deps,
        formats=formats,
    )
