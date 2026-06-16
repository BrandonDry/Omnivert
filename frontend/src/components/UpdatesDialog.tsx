import { useState, type ReactNode } from "react"
import { toast } from "sonner"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { UpdateSection } from "@/components/UpdateSection"
import {
  applyAppUpdate,
  applyUpdate,
  checkAppUpdate,
  checkUpdates,
  getAppUpdateStatus,
  getUpdateStatus,
} from "@/lib/api"
import type { AppUpdateInfo, UpdateInfo } from "@/lib/types"

export function UpdatesDialog({
  update,
  onUpdate,
  appUpdate,
  onAppUpdate,
  children,
}: {
  // Both info objects are owned by App (so the header badge can react); the dialog reports
  // fresh checks back up via the on*Update callbacks.
  update: UpdateInfo | null
  onUpdate: (info: UpdateInfo) => void
  appUpdate: AppUpdateInfo | null
  onAppUpdate: (info: AppUpdateInfo) => void
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const [checkingApp, setCheckingApp] = useState(false)
  const [checkingEngine, setCheckingEngine] = useState(false)

  async function checkApp() {
    setCheckingApp(true)
    try {
      const next = await checkAppUpdate()
      onAppUpdate(next)
      if (next.error) toast.error(next.error)
    } catch (e) {
      toast.error(`App update check failed: ${(e as Error).message}`)
    } finally {
      setCheckingApp(false)
    }
  }

  async function checkEngine() {
    setCheckingEngine(true)
    try {
      const next = await checkUpdates()
      onUpdate(next)
      if (next.error) toast.error(next.error)
    } catch (e) {
      toast.error(`Engine update check failed: ${(e as Error).message}`)
    } finally {
      setCheckingEngine(false)
    }
  }

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (next) {
      if (!appUpdate && !checkingApp) void checkApp()
      if (!update && !checkingEngine) void checkEngine()
    }
  }

  const appConfigured = !!appUpdate?.configured
  const appDownloadUrl = appUpdate?.download_url
  const appHasInstallerOrWheel = !!appDownloadUrl

  // When an app update is available it bundles a newer conversion engine; show that delta in
  // the app section so users see what actually improved (frozen builds act on this section,
  // not the engine one, which they can't apply directly).
  const engineInstalled = update?.installed
  const engineLatest = update?.latest
  const showEngineDelta =
    appConfigured &&
    !!appUpdate?.update_available &&
    !!engineInstalled &&
    !!engineLatest &&
    engineInstalled !== engineLatest

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Updates</DialogTitle>
          <DialogDescription>
            Omnivert (this app) and the conversion engine update
            independently. Installing an update always requires a restart.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 text-sm">
          <UpdateSection
            title="Omnivert (this app)"
            blurb="The app you're using now, installed from its GitHub releases."
            installed={appUpdate?.installed ?? null}
            latest={appUpdate?.latest ?? null}
            updateAvailable={!!appUpdate?.update_available}
            upToDate={
              appConfigured &&
              !appUpdate?.update_available &&
              !appUpdate?.error &&
              !!appUpdate?.installed
            }
            error={appUpdate?.error}
            releaseNotes={appUpdate?.release_notes}
            releaseUrl={appUpdate?.release_url}
            checking={checkingApp}
            onCheck={checkApp}
            apply={
              appConfigured
                ? {
                    label: `Update to ${appUpdate?.latest ?? ""}`,
                    canApply: !!appUpdate?.update_available && appHasInstallerOrWheel,
                    note: "This release has no installable build attached yet.",
                    start: () => applyAppUpdate(appDownloadUrl),
                    poll: getAppUpdateStatus,
                  }
                : undefined
            }
            footer={
              !appConfigured ? (
                <p className="text-xs text-muted-foreground">
                  Set your GitHub repository (owner/repo) in Settings to enable app update
                  checks.
                </p>
              ) : showEngineDelta ? (
                <p className="text-xs text-muted-foreground">
                  Includes the bundled conversion engine:{" "}
                  <span className="font-mono">{engineInstalled}</span> →{" "}
                  <span className="font-mono">{engineLatest}</span>.
                </p>
              ) : undefined
            }
          />

          <Separator />

          <UpdateSection
            title="Conversion engine"
            blurb="The bundled library that turns files into Markdown, from PyPI."
            installed={update?.installed ?? null}
            latest={update?.latest ?? null}
            updateAvailable={!!update?.update_available}
            upToDate={!update?.update_available && !update?.error && !!update?.installed}
            error={update?.error}
            releaseNotes={update?.release_notes}
            releaseUrl={update?.release_url}
            checking={checkingEngine}
            onCheck={checkEngine}
            apply={{
              label: `Update to ${update?.latest ?? ""}`,
              canApply: !!update?.update_available && (update?.can_apply ?? true),
              note: update?.apply_note,
              start: () => applyUpdate(update?.latest),
              poll: getUpdateStatus,
            }}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
