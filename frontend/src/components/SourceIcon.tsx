import {
  Archive,
  FileAudio,
  FileCode2,
  FileImage,
  FileJson,
  FileSpreadsheet,
  FileText,
  FileType,
  Globe,
  Mail,
  Presentation,
} from "lucide-react"

import { cn } from "@/lib/utils"

function sourceExtension(source: string): string {
  try {
    if (/^https?:\/\//i.test(source)) {
      const url = new URL(source)
      source = url.pathname
    }
  } catch {
    /* keep source as-is */
  }
  const clean = source.split(/[?#]/)[0] ?? ""
  const match = clean.match(/\.([a-z0-9]+)$/i)
  return match?.[1]?.toLowerCase() ?? ""
}

export function SourceIcon({
  source,
  className,
}: {
  source: string
  className?: string
}) {
  const ext = sourceExtension(source)
  const classes = cn("size-4 shrink-0 text-muted-foreground", className)

  if (/^https?:\/\//i.test(source)) return <Globe className={classes} />
  if (["png", "jpg", "jpeg", "gif", "bmp", "webp", "tif", "tiff", "svg"].includes(ext)) {
    return <FileImage className={classes} />
  }
  if (["mp3", "wav", "m4a", "flac", "ogg"].includes(ext)) return <FileAudio className={classes} />
  if (["zip", "epub"].includes(ext)) return <Archive className={classes} />
  if (["csv", "tsv", "xls", "xlsx"].includes(ext)) return <FileSpreadsheet className={classes} />
  if (["ppt", "pptx"].includes(ext)) return <Presentation className={classes} />
  if (["json", "jsonl"].includes(ext)) return <FileJson className={classes} />
  if (["html", "htm", "xml", "rss"].includes(ext)) return <FileCode2 className={classes} />
  if (["doc", "docx", "pdf", "txt", "md", "rtf"].includes(ext)) return <FileText className={classes} />
  if (["msg", "eml"].includes(ext)) return <Mail className={classes} />
  return <FileType className={classes} />
}
