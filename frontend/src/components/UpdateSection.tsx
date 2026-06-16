import { useEffect, useRef, useState } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ExternalLink,
  Loader2,
  RefreshCw,
  RotateCw,
} from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/Markdown"
import type { UpdateStatus } from "@/lib/types"

/** One product's update row (used for both the app and the conversion engine). It owns the
 *  install state machine — start the upgrade, then poll the matching status endpoint until
 *  it leaves `running` — so the parent dialog just wires in the product-specific calls. */
export interface UpdateApply {
  label: string
  canApply: boolean
  /** Shown instead of the button when an update exists but can't be applied here. */
  note?: string | null
  start: () => Promise<UpdateStatus>
  poll: () => Promise<UpdateStatus>
}

export function UpdateSection({
  title,
  blurb,
  installed,
  latest,
  updateAvailable,
  upToDate,
  error,
  releaseNotes,
  releaseUrl,
  checking,
  onCheck,
  apply,
  footer,
}: {
  title: string
  blurb: string
  installed: string | null
  latest: string | null
  updateAvailable: boolean
  upToDate: boolean
  error?: string | null
  releaseNotes?: string | null
  releaseUrl?: string | null
  checking: boolean
  onCheck: () => void
  apply?: UpdateApply
  footer?: React.ReactNode
}) {
  const [status, setStatus] = useState<UpdateStatus | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }
  useEffect(() => stopPolling, [])

  async function run() {
    if (!apply) return
    try {
      setStatus(await apply.start())
      stopPolling()
      pollRef.current = setInterval(async () => {
        try {
          const s = await apply.poll()
          setStatus(s)
          if (s.state !== "running") {
            stopPolling()
            if (s.state === "success") toast.success("Update installed — restart to finish")
            else if (s.state === "error") toast.error("Update failed")
          }
        } catch {
          /* transient; keep polling */
        }
      }, 1500)
    } catch (e) {
      toast.error(`Couldn't start update: ${(e as Error).message}`)
    }
  }

  const installing = status?.state === "running"

  return (
    <section className="space-y-3">
      <div>
        <h3 className="font-medium">{title}</h3>
        <p className="text-xs text-muted-foreground">{blurb}</p>
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div>
          <div className="text-xs text-muted-foreground">Installed</div>
          <div className="font-mono font-medium">{installed ?? "—"}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Latest</div>
          <div className="font-mono font-medium">{latest ?? "—"}</div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {upToDate && <Badge variant="muted">Up to date</Badge>}
          {updateAvailable && <Badge>Update available</Badge>}
          <Button variant="outline" size="sm" onClick={onCheck} disabled={checking || installing}>
            {checking ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Check now
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-amber-700 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {updateAvailable && !installing && status?.state !== "success" && apply && (
        <div className="flex flex-wrap items-center gap-3 rounded-md border bg-muted/20 p-3">
          <Download className="size-4 shrink-0 text-foreground" />
          <span className="flex-1">
            Update from <span className="font-mono">{installed}</span> to{" "}
            <span className="font-mono">{latest}</span>. The app must restart afterward.
          </span>
          {apply.canApply ? (
            <Button size="sm" onClick={run}>
              <Download />
              {apply.label}
            </Button>
          ) : (
            apply.note && <span className="text-xs text-muted-foreground">{apply.note}</span>
          )}
        </div>
      )}

      {status && (
        <div
          className={
            status.state === "error"
              ? "rounded-md border border-destructive/30 bg-destructive/10 p-3"
              : status.state === "success"
                ? "rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3"
                : "rounded-md border bg-muted/20 p-3"
          }
        >
          <div className="flex items-center gap-2 font-medium">
            {installing && <Loader2 className="size-4 animate-spin" />}
            {status.state === "success" && (
              <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
            )}
            {status.state === "error" && <AlertTriangle className="size-4 text-destructive" />}
            <span>{status.message}</span>
          </div>
          {status.state === "success" && (
            <div className="mt-2 flex items-center gap-2 text-muted-foreground">
              <RotateCw className="size-3.5" />
              <span>
                Close and reopen Omnivert to load
                {status.new_version ? ` v${status.new_version}` : " the new version"}.
              </span>
            </div>
          )}
          {status.output && (
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer text-muted-foreground">update details</summary>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] text-muted-foreground">
                {status.output}
              </pre>
            </details>
          )}
        </div>
      )}

      {releaseNotes ? (
        <div>
          <div className="mb-1 flex items-center justify-between">
            <h4 className="text-sm font-medium">Release notes — {latest}</h4>
            {releaseUrl && (
              <a
                href={releaseUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                View on GitHub <ExternalLink className="size-3" />
              </a>
            )}
          </div>
          <div className="max-h-56 overflow-auto rounded-md border bg-card/40 p-3">
            <Markdown>{releaseNotes}</Markdown>
          </div>
        </div>
      ) : (
        releaseUrl && (
          <a
            href={releaseUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            View releases on GitHub <ExternalLink className="size-3" />
          </a>
        )
      )}

      {footer}
    </section>
  )
}
