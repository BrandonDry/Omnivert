import { useEffect, useState } from "react"
import {
  Download,
  FileUp,
  FolderOpen,
  Inbox,
  Link as LinkIcon,
  Loader2,
  Sparkles,
  Type,
  X,
} from "lucide-react"
import { toast } from "sonner"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { FileDropzone } from "@/components/FileDropzone"
import { OptionsPanel } from "@/components/OptionsPanel"
import { ResultCard } from "@/components/ResultCard"
import { SourceIcon } from "@/components/SourceIcon"
import {
  convertFiles,
  convertFolder,
  convertPaths,
  convertText,
  convertUrl,
  downloadBatch,
  getNativeInfo,
  pickFiles,
  pickFolder,
  saveBatch,
} from "@/lib/api"
import type { ConversionResult, ConvertOptions } from "@/lib/types"

type Mode = "file" | "folder" | "url" | "text"

const TEXT_EXTENSIONS = [".txt", ".md", ".html", ".csv", ".json", ".xml", ".rss"]

interface Props {
  options: ConvertOptions
  onOptionsChange: (patch: Partial<ConvertOptions>) => void
  claudeKeySet: boolean
  azureDocIntelReady: boolean
  azureContentUnderstandingReady: boolean
  youtubeAvailable: boolean
}

export function ConvertPanel({
  options,
  onOptionsChange,
  claudeKeySet,
  azureDocIntelReady,
  azureContentUnderstandingReady,
  youtubeAvailable,
}: Props) {
  const [mode, setMode] = useState<Mode>("file")
  const [files, setFiles] = useState<File[]>([])
  const [nativePaths, setNativePaths] = useState<string[]>([])
  const [nativeDialogs, setNativeDialogs] = useState(false)
  const [folderPath, setFolderPath] = useState("")
  const [recursive, setRecursive] = useState(true)
  const [url, setUrl] = useState("")
  const [text, setText] = useState("")
  const [textExt, setTextExt] = useState(".txt")
  const [running, setRunning] = useState(false)
  const [picking, setPicking] = useState<"files" | "folder" | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [batchId, setBatchId] = useState<string | null>(null)
  const [results, setResults] = useState<ConversionResult[] | null>(null)

  useEffect(() => {
    getNativeInfo()
      .then((info) => setNativeDialogs(info.dialogs))
      .catch(() => setNativeDialogs(false))
  }, [])

  // Strip blank string hints so they don't override auto-detection on the backend.
  function cleanOptions(): ConvertOptions {
    return {
      ...options,
      extension: options.extension?.trim() || null,
      mimetype: options.mimetype?.trim() || null,
      charset: options.charset?.trim() || null,
    }
  }

  const canConvert =
    !running &&
    ((mode === "file" && (files.length > 0 || nativePaths.length > 0)) ||
      (mode === "folder" && folderPath.trim().length > 0) ||
      (mode === "url" && url.trim().length > 0) ||
      (mode === "text" && text.length > 0))

  async function run() {
    setRunning(true)
    setResults(null)
    setBatchId(null)
    try {
      if (mode === "file") {
        const batch =
          nativePaths.length > 0
            ? await convertPaths(nativePaths, cleanOptions())
            : await convertFiles(files, cleanOptions())
        setResults(batch.results)
        setBatchId(batch.batch_id)
      } else if (mode === "folder") {
        const batch = await convertFolder(folderPath.trim(), recursive, cleanOptions())
        setResults(batch.results)
        setBatchId(batch.batch_id)
      } else if (mode === "url") {
        setResults([await convertUrl(url.trim(), cleanOptions())])
      } else {
        setResults([
          await convertText(text, textExt, options.charset?.trim() || "utf-8", cleanOptions()),
        ])
      }
    } catch (e) {
      toast.error(`Conversion failed: ${(e as Error).message}`)
    } finally {
      setRunning(false)
    }
  }

  async function chooseFiles() {
    setPicking("files")
    try {
      const picked = await pickFiles()
      if (picked.paths.length > 0) {
        setNativePaths(picked.paths)
        setFiles([])
      }
    } catch (e) {
      toast.error(`Couldn't open file picker: ${(e as Error).message}`)
    } finally {
      setPicking(null)
    }
  }

  async function chooseFolder() {
    setPicking("folder")
    try {
      const picked = await pickFolder()
      if (picked.paths[0]) setFolderPath(picked.paths[0])
    } catch (e) {
      toast.error(`Couldn't open folder picker: ${(e as Error).message}`)
    } finally {
      setPicking(null)
    }
  }

  async function downloadAll() {
    if (!batchId) return
    setDownloading(true)
    try {
      if (nativeDialogs) {
        const saved = await saveBatch(batchId)
        toast[saved.path ? "success" : "info"](
          saved.path ? "Saved conversion output" : "Save canceled",
        )
        return
      }
      const { blob, filename } = await downloadBatch(batchId)
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = objectUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(objectUrl)
    } catch (e) {
      toast.error(`Download failed: ${(e as Error).message}`)
    } finally {
      setDownloading(false)
    }
  }

  const succeeded = results?.filter((r) => r.ok).length ?? 0
  const failed = results?.filter((r) => !r.ok).length ?? 0
  const canDownloadBatch = !!batchId && succeeded > 0

  const shortcutLabel = navigator.platform.toLowerCase().includes("mac") ? "Cmd+Enter" : "Ctrl+Enter"

  return (
    <div
      className="space-y-5"
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && canConvert) {
          e.preventDefault()
          void run()
        }
      }}
    >
      <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
        <TabsList className="w-full">
          <TabsTrigger value="file">
            <FileUp /> Files
          </TabsTrigger>
          <TabsTrigger value="folder">
            <FolderOpen /> Folder
          </TabsTrigger>
          <TabsTrigger value="url">
            <LinkIcon /> URL
          </TabsTrigger>
          <TabsTrigger value="text">
            <Type /> Text
          </TabsTrigger>
        </TabsList>

        <TabsContent value="file" className="mt-4">
          <div className="space-y-3">
            {nativeDialogs && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={chooseFiles}
                  disabled={running || picking !== null}
                >
                  {picking === "files" ? <Loader2 className="animate-spin" /> : <FileUp />}
                  Pick files
                </Button>
                {nativePaths.length > 0 && (
                  <span className="text-sm text-muted-foreground">
                    {nativePaths.length} native file{nativePaths.length > 1 ? "s" : ""} selected
                  </span>
                )}
                {nativePaths.length > 0 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setNativePaths([])}
                    disabled={running}
                  >
                    <X />
                    Clear
                  </Button>
                )}
              </div>
            )}
            <FileDropzone
              files={files}
              onChange={(next) => {
                setFiles(next)
                if (next.length > 0) setNativePaths([])
              }}
              disabled={running || nativePaths.length > 0}
            />
            {nativePaths.length > 0 && (
              <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                <div className="mb-1 font-medium text-foreground">Selected paths</div>
                <ul className="max-h-24 space-y-1 overflow-auto">
                  {nativePaths.map((path) => (
                    <li key={path} className="flex items-center gap-2" title={path}>
                      <SourceIcon source={path} />
                      <span className="truncate">{path}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="folder" className="mt-4 space-y-3">
          <div className="space-y-2">
            <Label htmlFor="folder-input">Folder path</Label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="folder-input"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                placeholder="D:\Projects\docs"
                disabled={running}
              />
              {nativeDialogs && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={chooseFolder}
                  disabled={running || picking !== null}
                >
                  {picking === "folder" ? <Loader2 className="animate-spin" /> : <FolderOpen />}
                  Pick folder
                </Button>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between rounded-md border bg-muted/20 px-3 py-2">
            <div>
              <Label htmlFor="recursive-folder">Include subfolders</Label>
              <p className="text-xs text-muted-foreground">
                Generated folders like node_modules, dist, .venv, and __pycache__ are skipped.
              </p>
            </div>
            <Switch
              id="recursive-folder"
              checked={recursive}
              onCheckedChange={setRecursive}
              disabled={running}
            />
          </div>
        </TabsContent>

        <TabsContent value="url" className="mt-4 space-y-2">
          <Label htmlFor="url-input">Page or media URL</Label>
          <Input
            id="url-input"
            type="url"
            placeholder="https://en.wikipedia.org/wiki/Markdown"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && canConvert) run()
            }}
          />
          <p className="text-xs text-muted-foreground">
            Webpages, Wikipedia, and RSS feeds work out of the box.{" "}
            {youtubeAvailable
              ? "YouTube transcript extraction is available."
              : "YouTube transcript extraction is not installed."}
          </p>
        </TabsContent>

        <TabsContent value="text" className="mt-4 space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="text-input">Paste content</Label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Interpret as</span>
              <Select value={textExt} onValueChange={setTextExt}>
                <SelectTrigger size="sm" className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TEXT_EXTENSIONS.map((ext) => (
                    <SelectItem key={ext} value={ext}>
                      {ext}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Textarea
            id="text-input"
            className="min-h-40 font-mono text-sm"
            placeholder="Paste HTML, CSV, JSON, XML, or Markdown here…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </TabsContent>
      </Tabs>

      <OptionsPanel
        options={options}
        onChange={onOptionsChange}
        claudeKeySet={claudeKeySet}
        azureDocIntelReady={azureDocIntelReady}
        azureContentUnderstandingReady={azureContentUnderstandingReady}
        showHints={mode === "file"}
      />

      <div className="flex items-center gap-3">
        <Button size="lg" onClick={run} disabled={!canConvert}>
          {running ? <Loader2 className="animate-spin" /> : <Sparkles />}
          {running ? "Converting…" : "Convert to Markdown"}
        </Button>
        <span className="hidden text-xs text-muted-foreground sm:inline">
          {shortcutLabel}
        </span>
        {mode === "file" && files.length > 1 && (
          <span className="text-sm text-muted-foreground">{files.length} files queued</span>
        )}
        {mode === "folder" && folderPath.trim() && (
          <span className="text-sm text-muted-foreground">
            {recursive ? "Recursive folder batch" : "Top-level folder batch"}
          </span>
        )}
      </div>

      {running && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/20 p-4 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          <span>Converting current {mode} input…</span>
        </div>
      )}

      {!running && !results && (
        <div className="flex items-start gap-3 rounded-lg border border-dashed bg-muted/10 p-4 text-sm text-muted-foreground">
          <Inbox className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium text-foreground">No conversion results yet</p>
            <p>Choose an input, adjust options, then convert to preview and download Markdown.</p>
          </div>
        </div>
      )}

      {!running && results && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Results</span>
              {succeeded > 0 && <span>· {succeeded} succeeded</span>}
              {failed > 0 && <span className="text-destructive">· {failed} failed</span>}
            </div>
            {canDownloadBatch && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={downloadAll}
                disabled={downloading}
              >
                {downloading ? <Loader2 className="animate-spin" /> : <Download />}
                Download all
              </Button>
            )}
          </div>
          {results.map((r, i) => (
            <ResultCard
              key={`${r.filename}-${i}`}
              result={r}
              nativeSaveAvailable={nativeDialogs}
            />
          ))}
        </div>
      )}
    </div>
  )
}
