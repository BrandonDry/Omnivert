// Types mirroring the FastAPI backend's Pydantic schemas (backend/schemas.py).

export type AzureBackend = "none" | "docintel" | "cu"

export interface ConvertOptions {
  extension?: string | null
  mimetype?: string | null
  charset?: string | null
  keep_data_uris: boolean
  enable_plugins: boolean
  describe_images: boolean
  azure_backend: AzureBackend
}

export interface ConversionResult {
  filename: string
  ok: boolean
  markdown?: string | null
  title?: string | null
  warnings: string[]
  error?: string | null
  error_kind?: string | null
  remediation?: string | null
}

export interface BatchResult {
  batch_id: string
  results: ConversionResult[]
}

export interface PickResult {
  paths: string[]
}

export interface SaveResult {
  path?: string | null
}

export interface NativeInfo {
  dialogs: boolean
}

export interface UpdateInfo {
  installed: string | null
  latest: string | null
  update_available: boolean
  channel: string
  release_notes?: string | null
  release_url?: string | null
  published_at?: string | null
  error?: string | null
  checked_at?: string | null
  can_apply: boolean
  apply_note?: string | null
}

export type UpdateState = "idle" | "running" | "success" | "error"

export interface UpdateStatus {
  state: UpdateState
  message?: string | null
  output?: string | null
  old_version?: string | null
  new_version?: string | null
  restart_required: boolean
}

export interface AppVersionInfo {
  version: string
  commit?: string | null
  frozen: boolean
}

export interface AppUpdateInfo {
  configured: boolean
  installed: string | null
  latest: string | null
  update_available: boolean
  repo?: string | null
  release_notes?: string | null
  release_url?: string | null
  download_url?: string | null
  installer_url?: string | null
  published_at?: string | null
  error?: string | null
  checked_at?: string | null
}

export interface PluginInfo {
  name: string
  value: string
}

export interface DependencyInfo {
  name: string
  installed: boolean
  version?: string | null
}

export interface FormatInfo {
  label: string
  extensions: string[]
  note?: string | null
}

export interface CapabilitiesResponse {
  engine_version: string | null
  python_version: string
  ffmpeg_available: boolean
  youtube_available: boolean
  dependencies: DependencyInfo[]
  formats: FormatInfo[]
}

// Settings come back redacted: secret fields are the sentinel "" and each has a
// companion has_<field> boolean. We keep this loose since the shape is a flat dict.
export interface Settings {
  docintel_endpoint: string
  docintel_key: string
  docintel_api_version: string
  cu_endpoint: string
  cu_key: string
  cu_analyzer_id: string
  cu_file_types: string[]
  claude_api_key: string
  claude_model: string
  claude_base_url: string
  llm_prompt: string
  exiftool_path: string
  style_map: string
  default_keep_data_uris: boolean
  default_enable_plugins: boolean
  default_describe_images: boolean
  default_azure_backend: AzureBackend
  theme: "light" | "dark" | "system"
  app_repo: string
  auto_check_updates: boolean
  skipped_app_version: string
  has_docintel_key?: boolean
  has_cu_key?: boolean
  has_claude_api_key?: boolean
}

export const REDACTED = "__REDACTED__"

export const DEFAULT_OPTIONS: ConvertOptions = {
  extension: "",
  mimetype: "",
  charset: "",
  keep_data_uris: false,
  enable_plugins: false,
  describe_images: false,
  azure_backend: "none",
}
