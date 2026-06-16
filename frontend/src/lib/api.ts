// Thin typed client over the Omnivert API. All paths are relative so the
// same build works behind the Vite dev proxy and the production static mount.

import type {
  AppUpdateInfo,
  AppVersionInfo,
  BatchResult,
  CapabilitiesResponse,
  ConversionResult,
  ConvertOptions,
  NativeInfo,
  PickResult,
  PluginInfo,
  SaveResult,
  Settings,
  UpdateInfo,
  UpdateStatus,
} from "./types"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === "string") return data.detail
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ")
    }
    return JSON.stringify(data)
  } catch {
    return res.statusText || `Request failed (${res.status})`
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json() as Promise<T>
}

async function sendJson<T>(path: string, method: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json() as Promise<T>
}

export function getCapabilities(): Promise<CapabilitiesResponse> {
  return getJson<CapabilitiesResponse>("/api/capabilities")
}

export function getPlugins(): Promise<PluginInfo[]> {
  return getJson<PluginInfo[]>("/api/plugins")
}

export function getSettings(): Promise<Settings> {
  return getJson<Settings>("/api/settings")
}

export function saveSettings(settings: Partial<Settings>): Promise<Settings> {
  return sendJson<Settings>("/api/settings", "PUT", settings)
}

export function getNativeInfo(): Promise<NativeInfo> {
  return getJson<NativeInfo>("/api/native")
}

export function checkUpdates(): Promise<UpdateInfo> {
  return getJson<UpdateInfo>("/api/updates/check")
}

export function applyUpdate(version?: string | null): Promise<UpdateStatus> {
  return sendJson<UpdateStatus>("/api/updates/apply", "POST", { version: version ?? null })
}

export function getUpdateStatus(): Promise<UpdateStatus> {
  return getJson<UpdateStatus>("/api/updates/status")
}

export function getAppVersion(): Promise<AppVersionInfo> {
  return getJson<AppVersionInfo>("/api/app/version")
}

export function checkAppUpdate(): Promise<AppUpdateInfo> {
  return getJson<AppUpdateInfo>("/api/app/updates/check")
}

export function applyAppUpdate(downloadUrl?: string | null): Promise<UpdateStatus> {
  return sendJson<UpdateStatus>("/api/app/updates/apply", "POST", {
    download_url: downloadUrl ?? null,
  })
}

export function getAppUpdateStatus(): Promise<UpdateStatus> {
  return getJson<UpdateStatus>("/api/app/updates/status")
}

export function pickFiles(): Promise<PickResult> {
  return sendJson<PickResult>("/api/pick-files", "POST", {})
}

export function pickFolder(): Promise<PickResult> {
  return sendJson<PickResult>("/api/pick-folder", "POST", {})
}

export function saveMarkdown(filename: string, content: string): Promise<SaveResult> {
  return sendJson<SaveResult>("/api/save-markdown", "POST", { filename, content })
}

export function saveBatch(batchId: string): Promise<SaveResult> {
  return sendJson<SaveResult>(`/api/save-download/${encodeURIComponent(batchId)}`, "POST", {})
}

export async function convertFiles(
  files: File[],
  options: ConvertOptions,
): Promise<BatchResult> {
  const form = new FormData()
  for (const file of files) form.append("files", file, file.name)
  form.append("options", JSON.stringify(options))
  const res = await fetch("/api/convert/file", { method: "POST", body: form })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json() as Promise<BatchResult>
}

export function convertPaths(paths: string[], options: ConvertOptions): Promise<BatchResult> {
  return sendJson<BatchResult>("/api/convert/paths", "POST", { paths, options })
}

export function convertFolder(
  path: string,
  recursive: boolean,
  options: ConvertOptions,
): Promise<BatchResult> {
  return sendJson<BatchResult>("/api/convert/folder", "POST", { path, recursive, options })
}

export function convertUrl(url: string, options: ConvertOptions): Promise<ConversionResult> {
  return sendJson<ConversionResult>("/api/convert/url", "POST", { url, options })
}

export function convertText(
  content: string,
  extension: string,
  charset: string,
  options: ConvertOptions,
): Promise<ConversionResult> {
  return sendJson<ConversionResult>("/api/convert/text", "POST", {
    content,
    extension,
    charset,
    options,
  })
}

export async function downloadBatch(batchId: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`/api/download/${encodeURIComponent(batchId)}`)
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  const disposition = res.headers.get("Content-Disposition") ?? ""
  const match = disposition.match(/filename="([^"]+)"/i)
  return {
    blob: await res.blob(),
    filename: match?.[1] ?? "omnivert-results.zip",
  }
}
