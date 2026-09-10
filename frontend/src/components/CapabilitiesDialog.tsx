import type { ReactNode } from "react"
import { Check, X } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import type { CapabilitiesResponse } from "@/lib/types"

function YesNo({ value }: { value: boolean }) {
  return value ? (
    <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
      <Check className="size-3.5" /> Yes
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-muted-foreground">
      <X className="size-3.5" /> No
    </span>
  )
}

export function CapabilitiesDialog({
  caps,
  children,
}: {
  caps: CapabilitiesResponse | null
  children: ReactNode
}) {
  // Which distributions actually imported, so a format can name the dependency it is
  // waiting on rather than just failing silently.
  const installed = new Map((caps?.dependencies ?? []).map((d) => [d.name, d.installed]))
  const brokenFormats = (caps?.formats ?? []).filter((f) => !f.available)

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Capabilities</DialogTitle>
          <DialogDescription>
            What this conversion engine can handle, and which optional dependencies are
            present.
          </DialogDescription>
        </DialogHeader>

        {!caps ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="space-y-5 text-sm">
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
              <div>
                <div className="text-xs text-muted-foreground">Engine</div>
                <div className="font-medium">{caps.engine_version ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Python</div>
                <div className="font-medium">{caps.python_version}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">ffmpeg</div>
                <div className="font-medium">
                  <YesNo value={caps.ffmpeg_available} />
                </div>
              </div>
            </div>

            <div>
              <h3 className="mb-2 font-medium">Supported formats</h3>
              <div className="flex flex-wrap gap-1.5">
                {caps.formats.map((f) => {
                  const missing = f.requires.filter(
                    (dist) => !installed.get(dist),
                  )
                  return (
                    <Badge
                      key={f.label}
                      variant={f.available ? "secondary" : "outline"}
                      className={
                        f.available ? undefined : "border-destructive/50 text-destructive"
                      }
                      title={
                        [
                          f.extensions.join(", "),
                          f.note,
                          missing.length > 0
                            ? `Unavailable: ${missing.join(", ")} not installed`
                            : null,
                        ]
                          .filter(Boolean)
                          .join(" · ") || undefined
                      }
                    >
                      {f.label}
                      {!f.available && " (unavailable)"}
                    </Badge>
                  )
                })}
              </div>
              {brokenFormats.length > 0 && (
                <p className="mt-2 text-xs text-destructive">
                  {brokenFormats.length} format
                  {brokenFormats.length > 1 ? "s are" : " is"} unavailable because a
                  dependency is missing. Every dependency below ships with Omnivert, so
                  anything marked missing means a broken install: reinstall to repair it.
                </p>
              )}
            </div>

            <div>
              <h3 className="mb-2 font-medium">Optional dependencies</h3>
              <ul className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
                {caps.dependencies.map((d) => (
                  <li key={d.name} className="flex items-center justify-between gap-2">
                    <span
                      className="truncate font-mono text-xs"
                      title={d.gates ? `${d.name} — enables ${d.gates}` : d.name}
                    >
                      {d.name}
                    </span>
                    <span className="shrink-0 text-xs">
                      {d.installed ? (
                        <span className="text-emerald-600 dark:text-emerald-400">
                          {d.version ?? "installed"}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">missing</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <div className="mt-2 flex items-center gap-2 border-t pt-3">
          <img src="/favicon.svg" alt="" className="size-5" />
          <span className="text-sm font-medium">Omnivert</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Conversion is powered by Microsoft{" "}
          <a
            href="https://github.com/microsoft/markitdown"
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            MarkItDown
          </a>{" "}
          (MIT License, © Microsoft Corporation). Omnivert is an independent project, not
          affiliated with Microsoft.
        </p>
      </DialogContent>
    </Dialog>
  )
}
