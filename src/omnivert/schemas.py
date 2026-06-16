"""Pydantic request/response models for the Omnivert API."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

AzureBackend = Literal["none", "docintel", "cu"]


class ConvertOptions(BaseModel):
    """Per-conversion options shared by every input mode."""

    extension: Optional[str] = Field(
        default=None, description="File-extension hint, e.g. '.pdf' (added if missing)."
    )
    mimetype: Optional[str] = Field(default=None, description="MIME-type hint.")
    charset: Optional[str] = Field(default=None, description="Charset hint, e.g. 'utf-8'.")
    keep_data_uris: bool = Field(
        default=False, description="Keep base64 data URIs instead of truncating them."
    )
    enable_plugins: bool = Field(default=False, description="Enable 3rd-party plugins.")
    describe_images: bool = Field(
        default=False, description="Describe images with Claude (needs an API key)."
    )
    azure_backend: AzureBackend = Field(
        default="none", description="Optional Azure extraction backend."
    )


class UrlConvertRequest(BaseModel):
    url: str
    options: ConvertOptions = Field(default_factory=ConvertOptions)


class TextConvertRequest(BaseModel):
    content: str
    extension: Optional[str] = ".txt"
    charset: Optional[str] = "utf-8"
    options: ConvertOptions = Field(default_factory=ConvertOptions)


class FolderConvertRequest(BaseModel):
    """Convert every file in a local folder (optionally recursing into subfolders)."""

    path: str
    recursive: bool = False
    options: ConvertOptions = Field(default_factory=ConvertOptions)


class PathsConvertRequest(BaseModel):
    """Convert a list of local file paths (e.g. from the native file picker)."""

    paths: List[str]
    options: ConvertOptions = Field(default_factory=ConvertOptions)


class ConversionResult(BaseModel):
    """Uniform result for every conversion; ``error`` is set instead of ``markdown``
    when a single item fails, so batches can be partially successful."""

    filename: str
    ok: bool = True
    markdown: Optional[str] = None
    title: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    error_kind: Optional[str] = None
    remediation: Optional[str] = None


class BatchResult(BaseModel):
    """A group of conversions plus an id the client can use to download them as a
    single ``.zip`` (or ``.md`` when only one succeeded) via ``GET /api/download/{id}``."""

    batch_id: str
    results: List[ConversionResult]


class PickResult(BaseModel):
    """Outcome of a native pick dialog. ``paths`` is empty when the user cancels."""

    paths: List[str] = Field(default_factory=list)


class SaveMarkdownRequest(BaseModel):
    """Markdown content to save through the native desktop save dialog."""

    filename: str
    content: str


class SaveResult(BaseModel):
    """Outcome of a native save dialog. ``path`` is null when the user cancels."""

    path: Optional[str] = None


class NativeInfo(BaseModel):
    """Whether the native (pywebview) pick dialogs are available in this process."""

    dialogs: bool


class UpdateInfo(BaseModel):
    """Result of an update check against PyPI (with GitHub release notes for review)."""

    installed: Optional[str] = None
    latest: Optional[str] = None
    update_available: bool = False
    channel: str = "pypi"
    release_notes: Optional[str] = None
    release_url: Optional[str] = None
    published_at: Optional[str] = None
    error: Optional[str] = None
    checked_at: Optional[str] = None
    can_apply: bool = True
    apply_note: Optional[str] = None


class UpdateApplyRequest(BaseModel):
    """Optional pinned version to install; ``None`` installs the latest available."""

    version: Optional[str] = None


class UpdateStatus(BaseModel):
    """Progress of a background ``pip install`` upgrade (engine or app)."""

    state: Literal["idle", "running", "success", "error"] = "idle"
    message: Optional[str] = None
    output: Optional[str] = None
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    restart_required: bool = False


class AppVersionInfo(BaseModel):
    """The running Omnivert app version (+ git commit when from a checkout)."""

    version: str
    commit: Optional[str] = None
    frozen: bool = False


class AppUpdateInfo(BaseModel):
    """Result of an app self-update check against the configured GitHub repo."""

    configured: bool = False
    installed: Optional[str] = None
    latest: Optional[str] = None
    update_available: bool = False
    repo: Optional[str] = None
    release_notes: Optional[str] = None
    release_url: Optional[str] = None
    download_url: Optional[str] = None
    installer_url: Optional[str] = None
    published_at: Optional[str] = None
    error: Optional[str] = None
    checked_at: Optional[str] = None


class AppUpdateApplyRequest(BaseModel):
    """Wheel asset URL to install (from the GitHub release)."""

    download_url: Optional[str] = None


class PluginInfo(BaseModel):
    name: str
    value: str


class DependencyInfo(BaseModel):
    name: str
    installed: bool
    version: Optional[str] = None


class FormatInfo(BaseModel):
    label: str
    extensions: List[str]
    note: Optional[str] = None


class CapabilitiesResponse(BaseModel):
    engine_version: Optional[str]
    python_version: str
    ffmpeg_available: bool
    youtube_available: bool
    dependencies: List[DependencyInfo]
    formats: List[FormatInfo]
