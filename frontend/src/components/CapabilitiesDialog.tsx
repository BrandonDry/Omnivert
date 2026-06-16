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
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
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
              <div>
                <div className="text-xs text-muted-foreground">YouTube</div>
                <div className="font-medium">
                  <YesNo value={caps.youtube_available} />
                </div>
              </div>
            </div>

            <div>
              <h3 className="mb-2 font-medium">Supported formats</h3>
              <div className="flex flex-wrap gap-1.5">
                {caps.formats.map((f) => (
                  <Badge
                    key={f.label}
                    variant="secondary"
                    title={
                      [f.extensions.join(", "), f.note].filter(Boolean).join(" — ") ||
                      undefined
                    }
                  >
                    {f.label}
                  </Badge>
                ))}
              </div>
            </div>

            <div>
              <h3 className="mb-2 font-medium">Optional dependencies</h3>
              <ul className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
                {caps.dependencies.map((d) => (
                  <li key={d.name} className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs" title={d.name}>
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
