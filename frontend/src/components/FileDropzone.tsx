import { useRef, useState } from "react"
import { Upload, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { SourceIcon } from "@/components/SourceIcon"
import { cn } from "@/lib/utils"

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

interface Props {
  files: File[]
  onChange: (files: File[]) => void
  disabled?: boolean
}

export function FileDropzone({ files, onChange, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function addFiles(incoming: FileList | null) {
    if (!incoming || incoming.length === 0) return
    // Append, de-duplicating on name+size so re-dropping the same file is a no-op.
    const merged = [...files]
    for (const f of Array.from(incoming)) {
      if (!merged.some((m) => m.name === f.name && m.size === f.size)) merged.push(f)
    }
    onChange(merged)
  }

  function removeAt(index: number) {
    onChange(files.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!disabled && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!disabled) addFiles(e.dataTransfer.files)
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <Upload className="size-7 text-muted-foreground" />
        <div className="text-sm">
          <span className="font-medium text-foreground">Click to choose files</span>{" "}
          <span className="text-muted-foreground">or drag and drop</span>
        </div>
        <p className="text-xs text-muted-foreground">
          PDF, Office docs, images, audio, HTML, CSV, JSON, EPUB, ZIP…
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files)
            e.target.value = "" // allow re-selecting the same file
          }}
        />
      </div>

      {files.length > 0 && (
        <ul className="space-y-1.5">
          {files.map((file, i) => (
            <li
              key={`${file.name}-${file.size}-${i}`}
              className="flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-sm"
            >
              <SourceIcon source={file.name} />
              <span className="flex-1 truncate" title={file.name}>
                {file.name}
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {formatBytes(file.size)}
              </span>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => removeAt(i)}
                disabled={disabled}
                aria-label={`Remove ${file.name}`}
              >
                <X />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
