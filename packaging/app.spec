# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"
WEB = SRC / "omnivert" / "web"
ICON = ROOT / "packaging" / "omnivert.ico"  # exe/window/taskbar icon


def safe_collect_data_files(package):
    try:
        return collect_data_files(package)
    except Exception:
        return []


def safe_collect_submodules(package):
    try:
        return collect_submodules(package)
    except Exception:
        return []


datas = []
if WEB.exists():
    datas.append((str(WEB), "web"))

# Ship license + attribution notices alongside the frozen app.
for notice in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
    notice_path = ROOT / notice
    if notice_path.exists():
        datas.append((str(notice_path), "."))

for package in (
    "markitdown",
    "magika",
    "onnxruntime",
    "pdfminer",
    "pdfplumber",
    "mammoth",
):
    datas += safe_collect_data_files(package)


def safe_copy_metadata(package, recursive=False):
    try:
        return copy_metadata(package, recursive=recursive)
    except Exception:
        return []


# Bundle package metadata so importlib.metadata.version(...) works in the frozen app
# (drives the Capabilities dialog engine/dependency versions). Recursive picks up the
# engine's dependencies too.
datas += safe_copy_metadata("markitdown", recursive=True)

# Explicit metadata for the optional deps surfaced in the Capabilities dialog
# (these are markitdown extras, not followed by the recursive pass above). Keep in sync
# with _OPTIONAL_DEPS in src/omnivert/capabilities.py.
for dist_name in (
    "pdfminer.six",
    "pdfplumber",
    "mammoth",
    "python-pptx",
    "openpyxl",
    "xlrd",
    "magika",
    "Pillow",
    "pydub",
    "SpeechRecognition",
    "azure-ai-documentintelligence",
    "azure-ai-contentunderstanding",
    "openai",
    "youtube-transcript-api",
):
    datas += safe_copy_metadata(dist_name)

hiddenimports = []
for package in (
    "markitdown",
    "uvicorn",
    "webview",
    "magika",
    "onnxruntime",
):
    hiddenimports += safe_collect_submodules(package)

a = Analysis(
    [str(ROOT / "packaging" / "freeze_entry.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Omnivert",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ICON) if ICON.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Omnivert",
)

