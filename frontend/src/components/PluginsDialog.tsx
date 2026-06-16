import { useState, type ReactNode } from "react"
import { Loader2, Plug, RefreshCw, SearchCode } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { getPlugins } from "@/lib/api"
import type { PluginInfo } from "@/lib/types"

export function PluginsDialog({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [plugins, setPlugins] = useState<PluginInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setLoading(true)
    setError(null)
    getPlugins()
      .then(setPlugins)
      .catch((e) => {
        const message = (e as Error).message
        setError(message)
        toast.error(`Couldn't load plugins: ${message}`)
      })
      .finally(() => setLoading(false))
  }

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (next && plugins === null && !loading) load()
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Plugins</DialogTitle>
          <DialogDescription>
            Installed third-party converters discovered from the engine plugin entry-point group.
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="flex items-center justify-center rounded-md border bg-muted/20 py-10 text-sm text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            Loading plugins…
          </div>
        )}

        {!loading && error && (
          <div className="space-y-3 rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm">
            <div>
              <p className="font-medium text-destructive">Plugins could not be loaded.</p>
              <p className="mt-1 text-muted-foreground">{error}</p>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={load}>
              <RefreshCw />
              Retry
            </Button>
          </div>
        )}

        {!loading && !error && plugins?.length === 0 && (
          <div className="space-y-4 rounded-md border bg-muted/20 p-4 text-sm">
            <div className="flex items-start gap-3">
              <div className="rounded-md border bg-background p-2">
                <Plug className="size-4 text-muted-foreground" />
              </div>
              <div>
                <p className="font-medium">No converter plugins are installed.</p>
                <p className="mt-1 text-muted-foreground">
                  Install plugin packages into this workspace venv, then enable plugins in
                  conversion options or Settings defaults.
                </p>
              </div>
            </div>
            <div className="rounded-md bg-background p-3 font-mono text-xs">
              .\.venv\Scripts\python -m pip install &lt;plugin-package&gt;
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <SearchCode className="size-3.5" />
              Search package indexes for converter plugins tagged markitdown-plugin.
            </div>
          </div>
        )}

        {!loading && !error && plugins && plugins.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Installed plugins</p>
              <Badge variant="secondary">
                {plugins.length} found
              </Badge>
            </div>
            <ul className="space-y-2">
              {plugins.map((plugin) => (
                <li key={`${plugin.name}-${plugin.value}`} className="rounded-md border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Plug className="size-4 text-muted-foreground" />
                    <span className="font-medium">{plugin.name}</span>
                  </div>
                  <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                    {plugin.value}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
