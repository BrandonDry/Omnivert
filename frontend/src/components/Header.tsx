import { Info, Plug, RefreshCw, Settings as SettingsIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ThemeToggle } from "@/components/ThemeToggle"
import { CapabilitiesDialog } from "@/components/CapabilitiesDialog"
import { PluginsDialog } from "@/components/PluginsDialog"
import { SettingsDialog } from "@/components/SettingsDialog"
import { UpdatesDialog } from "@/components/UpdatesDialog"
import type { AppUpdateInfo, CapabilitiesResponse, Settings, UpdateInfo } from "@/lib/types"

export function Header({
  caps,
  update,
  onUpdate,
  appUpdate,
  onAppUpdate,
  onSettingsSaved,
}: {
  caps: CapabilitiesResponse | null
  update: UpdateInfo | null
  onUpdate: (info: UpdateInfo) => void
  appUpdate: AppUpdateInfo | null
  onAppUpdate: (info: AppUpdateInfo) => void
  onSettingsSaved: (settings: Settings) => void
}) {
  const appUpdateAvailable = !!appUpdate?.update_available
  const updateAvailable = appUpdateAvailable || !!update?.update_available

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3">
        <img src="/favicon.svg" alt="" className="size-7" />
        <div className="flex flex-1 items-center gap-2">
          <h1 className="text-base font-semibold tracking-tight">Omnivert</h1>
          {caps?.engine_version && (
            <Badge variant="muted" className="font-mono">
              v{caps.engine_version}
            </Badge>
          )}
        </div>

        <CapabilitiesDialog caps={caps}>
          <Button variant="ghost" size="sm">
            <Info />
            Capabilities
          </Button>
        </CapabilitiesDialog>

        <PluginsDialog>
          <Button variant="ghost" size="sm">
            <Plug />
            Plugins
          </Button>
        </PluginsDialog>

        <UpdatesDialog
          update={update}
          onUpdate={onUpdate}
          appUpdate={appUpdate}
          onAppUpdate={onAppUpdate}
        >
          <Button
            variant="ghost"
            size="sm"
            className="relative"
            title={
              appUpdateAvailable
                ? `App update available: v${appUpdate?.latest}`
                : updateAvailable
                  ? `Engine update available: v${update?.latest}`
                  : "Check for updates"
            }
          >
            <RefreshCw />
            Updates
            {updateAvailable && (
              <span className="absolute right-1 top-1 size-2 rounded-full bg-primary ring-2 ring-background" />
            )}
          </Button>
        </UpdatesDialog>

        <SettingsDialog onSaved={onSettingsSaved}>
          <Button variant="ghost" size="icon" aria-label="Settings">
            <SettingsIcon />
          </Button>
        </SettingsDialog>

        <ThemeToggle />
      </div>
    </header>
  )
}
