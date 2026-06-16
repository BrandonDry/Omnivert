import { useCallback, useEffect, useRef, useState } from "react"

import { Header } from "@/components/Header"
import { ConvertPanel } from "@/components/ConvertPanel"
import { checkAppUpdate, checkUpdates, getCapabilities, getSettings } from "@/lib/api"
import { useTheme, type Theme } from "@/lib/theme"
import {
  DEFAULT_OPTIONS,
  type AppUpdateInfo,
  type CapabilitiesResponse,
  type ConvertOptions,
  type Settings,
  type UpdateInfo,
} from "@/lib/types"

function cloudBackendReady(s: Settings, backend: ConvertOptions["azure_backend"]) {
  if (backend === "docintel") return !!s.docintel_endpoint?.trim() && !!s.has_docintel_key
  if (backend === "cu") return !!s.cu_endpoint?.trim() && !!s.has_cu_key
  return true
}

function App() {
  const { setTheme } = useTheme()
  const [caps, setCaps] = useState<CapabilitiesResponse | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [options, setOptions] = useState<ConvertOptions>(DEFAULT_OPTIONS)
  const [update, setUpdate] = useState<UpdateInfo | null>(null)
  const [appUpdate, setAppUpdate] = useState<AppUpdateInfo | null>(null)
  // Latest settings + last-check time, read by the in-session re-check timer/listeners
  // without re-subscribing them on every settings change.
  const settingsRef = useRef<Settings | null>(null)
  const lastCheckRef = useRef(0)

  // Quiet update checks for both the app and the engine (opt-out via Settings). Failures
  // (offline) just leave the badge off; a release the user chose to skip won't light it.
  // Throttled so frequent window refocus can't spam the API — `force` bypasses it for the
  // launch-time check.
  const runUpdateChecks = useCallback((s: Settings, force = false) => {
    if (s.auto_check_updates === false) return
    const now = Date.now()
    if (!force && now - lastCheckRef.current < 60 * 60 * 1000) return
    lastCheckRef.current = now
    checkUpdates()
      .then(setUpdate)
      .catch(() => setUpdate(null))
    checkAppUpdate()
      .then((info) =>
        setAppUpdate(
          info.latest && info.latest === s.skipped_app_version
            ? { ...info, update_available: false }
            : info,
        ),
      )
      .catch(() => setAppUpdate(null))
  }, [])

  // Seed UI defaults and theme from saved settings; capabilities populate the header
  // badge and the Capabilities dialog.
  useEffect(() => {
    getCapabilities()
      .then(setCaps)
      .catch(() => setCaps(null))

    getSettings()
      .then((s) => {
        applySettings(s)
        settingsRef.current = s
        setOptions((o) => ({
          ...o,
          keep_data_uris: s.default_keep_data_uris,
          enable_plugins: s.default_enable_plugins,
          describe_images: s.default_describe_images && !!s.has_claude_api_key,
          azure_backend: cloudBackendReady(s, s.default_azure_backend)
            ? s.default_azure_backend
            : "none",
        }))
        runUpdateChecks(s, true)
      })
      .catch(() => setSettings(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // In-session re-check: a long-running window (the app can stay open for days) learns about
  // a new release without a restart — on a ~24h timer and when the window regains focus.
  useEffect(() => {
    const tick = () => {
      const s = settingsRef.current
      if (s) runUpdateChecks(s)
    }
    const onVisible = () => {
      if (document.visibilityState === "visible") tick()
    }
    const id = setInterval(tick, 24 * 60 * 60 * 1000)
    document.addEventListener("visibilitychange", onVisible)
    window.addEventListener("focus", onVisible)
    return () => {
      clearInterval(id)
      document.removeEventListener("visibilitychange", onVisible)
      window.removeEventListener("focus", onVisible)
    }
  }, [runUpdateChecks])

  function applySettings(s: Settings) {
    setSettings(s)
    settingsRef.current = s
    setTheme(s.theme as Theme)
    setOptions((o) => ({
      ...o,
      describe_images: o.describe_images && !!s.has_claude_api_key,
      azure_backend: cloudBackendReady(s, o.azure_backend) ? o.azure_backend : "none",
    }))
  }

  const claudeKeySet = !!settings?.has_claude_api_key
  const azureDocIntelReady = settings ? cloudBackendReady(settings, "docintel") : false
  const azureContentUnderstandingReady = settings ? cloudBackendReady(settings, "cu") : false

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header
        caps={caps}
        update={update}
        onUpdate={setUpdate}
        appUpdate={appUpdate}
        onAppUpdate={setAppUpdate}
        onSettingsSaved={applySettings}
      />
      <main className="mx-auto max-w-5xl px-4 py-6">
        <p className="mb-5 text-sm text-muted-foreground">
          Convert files, URLs, or pasted text into clean Markdown for LLMs.
        </p>
        <ConvertPanel
          options={options}
          onOptionsChange={(patch) => setOptions((o) => ({ ...o, ...patch }))}
          claudeKeySet={claudeKeySet}
          azureDocIntelReady={azureDocIntelReady}
          azureContentUnderstandingReady={azureContentUnderstandingReady}
          youtubeAvailable={!!caps?.youtube_available}
        />
      </main>
    </div>
  )
}

export default App
