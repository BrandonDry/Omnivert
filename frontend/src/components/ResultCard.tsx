import { useState } from "react"
import {
  AlertTriangle,
  Check,
  Copy,
  Download,
  Eye,
  CircleAlert,
  Code,
  Lightbulb,
} from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/Markdown"
import { SourceIcon } from "@/components/SourceIcon"
import { saveMarkdown } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { ConversionResult } from "@/lib/types"

function downloadName(result: ConversionResult): string {
  // Turn the source label (filename or URL) into a sensible .md filename.
  let base = result.title?.trim() || result.filename || "converted"
  try {
    if (/^https?:\/\//i.test(base)) {
      const u = new URL(base)
      base = u.hostname + u.pathname.replace(/\/$/, "").replace(/\//g, "-")
    }
  } catch {
    /* not a URL; use as-is */
  }
  base = base.replace(/\.[^./\\]+$/, "") // drop trailing extension
  base = base.replace(/[\\/:*?"<>|]+/g, "_").replace(/^_+|_+$/g, "") || "converted"
  return `${base}.md`
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      toast.success("Copied to clipboard")
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error("Couldn't copy to clipboard")
    }
  }
  return (
    <Button variant="outline" size="sm" onClick={copy}>
      {copied ? <Check /> : <Copy />}
      {copied ? "Copied" : "Copy"}
    </Button>
  )
}

export function ResultCard({
  result,
  nativeSaveAvailable = false,
}: {
  result: ConversionResult
  nativeSaveAvailable?: boolean
}) {
  const [view, setView] = useState<"preview" | "raw">("preview")
  const markdown = result.markdown ?? ""

  async function download() {
    const filename = downloadName(result)
    if (nativeSaveAvailable) {
      try {
        const saved = await saveMarkdown(filename, markdown)
        toast[saved.path ? "success" : "info"](
          saved.path ? `Saved ${filename}` : "Save canceled",
        )
        return
      } catch (e) {
        toast.error(`Save failed: ${(e as Error).message}`)
        return
      }
    }
    try {
      const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      toast.error(`Download failed: ${(e as Error).message}`)
    }
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b bg-muted/40 px-4 py-2.5">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {result.ok ? (
            <SourceIcon
              source={result.filename}
              className="text-emerald-600 dark:text-emerald-400"
            />
          ) : (
            <CircleAlert className="size-4 shrink-0 text-destructive" />
          )}
          <span className="truncate text-sm font-medium" title={result.filename}>
            {result.title?.trim() || result.filename}
          </span>
        </div>

        {result.warnings.length > 0 && (
          <Badge variant="muted" title={result.warnings.join("\n")}>
            <AlertTriangle />
            {result.warnings.length} warning{result.warnings.length > 1 ? "s" : ""}
          </Badge>
        )}

        {result.ok && (
          <div className="flex items-center gap-1.5">
            <div className="flex rounded-md border p-0.5">
              <button
                type="button"
                onClick={() => setView("preview")}
                className={cn(
                  "flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium",
                  view === "preview"
                    ? "bg-secondary text-secondary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Eye className="size-3" />
                Preview
              </button>
              <button
                type="button"
                onClick={() => setView("raw")}
                className={cn(
                  "flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium",
                  view === "raw"
                    ? "bg-secondary text-secondary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Code className="size-3" />
                Raw
              </button>
            </div>
            <CopyButton text={markdown} />
            <Button variant="outline" size="sm" onClick={() => void download()}>
              <Download />
              .md
            </Button>
          </div>
        )}
      </div>

      {result.ok ? (
        <div className="max-h-[28rem] space-y-3 overflow-auto p-4">
          {result.warnings.length > 0 && (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
              <div className="mb-1 flex items-center gap-2 font-medium text-amber-700 dark:text-amber-300">
                <AlertTriangle className="size-4" />
                Conversion completed with warnings
              </div>
              <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                {result.warnings.slice(0, 3).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {markdown.trim().length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              Conversion produced no text content.
            </p>
          ) : view === "preview" ? (
            <Markdown>{markdown}</Markdown>
          ) : (
            <pre className="text-xs whitespace-pre-wrap break-words font-mono">
              {markdown}
            </pre>
          )}
        </div>
      ) : (
        <div className="space-y-2 p-4">
          <div className="flex items-center gap-2">
            <Badge variant="destructive">{result.error_kind ?? "error"}</Badge>
          </div>
          <p className="text-sm font-medium text-destructive">{result.error}</p>
          {result.remediation && (
            <div className="flex items-start gap-2 rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
              <Lightbulb className="mt-0.5 size-4 shrink-0" />
              <p>{result.remediation}</p>
            </div>
          )}
        </div>
      )}

      {result.warnings.length > 0 && (
        <details className="border-t bg-muted/20 px-4 py-2 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">
            Warnings
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
