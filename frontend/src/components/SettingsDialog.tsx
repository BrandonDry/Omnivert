import { useState, type ReactNode } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { getSettings, saveSettings } from "@/lib/api"
import { REDACTED, type AzureBackend, type Settings } from "@/lib/types"
import { useTheme, type Theme } from "@/lib/theme"

const SECRET_FIELDS = ["claude_api_key", "docintel_key", "cu_key"] as const

interface Props {
  children: ReactNode
  onSaved: (settings: Settings) => void
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-semibold">{children}</h3>
}

export function SettingsDialog({ children, onSaved }: Props) {
  const { setTheme } = useTheme()
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState<Settings | null>(null)
  // Saved-secret indicators (whether a key already exists on the backend).
  const [has, setHas] = useState<Record<string, boolean>>({})

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) return
    setLoading(true)
    getSettings()
      .then((s) => {
        setHas({
          claude_api_key: !!s.has_claude_api_key,
          docintel_key: !!s.has_docintel_key,
          cu_key: !!s.has_cu_key,
        })
        // Blank the secret inputs; the user types only to change them.
        setDraft({ ...s, claude_api_key: "", docintel_key: "", cu_key: "" })
      })
      .catch((e) => toast.error(`Couldn't load settings: ${e.message}`))
      .finally(() => setLoading(false))
  }

  function patch(p: Partial<Settings>) {
    setDraft((d) => (d ? { ...d, ...p } : d))
  }

  async function handleSave() {
    if (!draft) return
    setSaving(true)
    // Preserve existing secrets when the input was left blank.
    const payload: Partial<Settings> = { ...draft }
    for (const f of SECRET_FIELDS) {
      if (!payload[f]) payload[f] = REDACTED as never
    }
    try {
      const saved = await saveSettings(payload)
      setTheme(saved.theme as Theme)
      onSaved(saved)
      toast.success("Settings saved")
      setOpen(false)
    } catch (e) {
      toast.error(`Couldn't save settings: ${(e as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-h-[88vh] overflow-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            API keys are stored locally and never leave this machine. Secret fields show a
            placeholder when a value is already saved — leave them blank to keep it.
          </DialogDescription>
        </DialogHeader>

        {loading || !draft ? (
          <div className="flex items-center justify-center py-10 text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" /> Loading…
          </div>
        ) : (
          <div className="space-y-6 py-1">
            {/* Appearance */}
            <section className="space-y-3">
              <SectionTitle>Appearance</SectionTitle>
              <Field label="Theme">
                <Select
                  value={draft.theme}
                  onValueChange={(v) => {
                    patch({ theme: v as Settings["theme"] })
                    setTheme(v as Theme)
                  }}
                >
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="system">System</SelectItem>
                    <SelectItem value="light">Light</SelectItem>
                    <SelectItem value="dark">Dark</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </section>

            <Separator />

            {/* Claude image captioning */}
            <section className="space-y-3">
              <SectionTitle>Claude (image captioning)</SectionTitle>
              <Field
                label="API key"
                hint={
                  has.claude_api_key
                    ? "A key is saved. Type to replace it."
                    : "Required for the “Describe images with Claude” option."
                }
              >
                <Input
                  type="password"
                  autoComplete="off"
                  placeholder={has.claude_api_key ? "•••••••••• (saved)" : "sk-ant-…"}
                  value={draft.claude_api_key}
                  onChange={(e) => patch({ claude_api_key: e.target.value })}
                />
              </Field>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="Model">
                  <Input
                    value={draft.claude_model}
                    onChange={(e) => patch({ claude_model: e.target.value })}
                  />
                </Field>
                <Field label="Base URL">
                  <Input
                    value={draft.claude_base_url}
                    onChange={(e) => patch({ claude_base_url: e.target.value })}
                  />
                </Field>
              </div>
              <Field label="Caption prompt" hint="Optional override for the image-caption prompt.">
                <Textarea
                  rows={2}
                  value={draft.llm_prompt}
                  onChange={(e) => patch({ llm_prompt: e.target.value })}
                />
              </Field>
            </section>

            <Separator />

            {/* Azure Document Intelligence */}
            <section className="space-y-3">
              <SectionTitle>Azure Document Intelligence</SectionTitle>
              <Field label="Endpoint">
                <Input
                  placeholder="https://<resource>.cognitiveservices.azure.com/"
                  value={draft.docintel_endpoint}
                  onChange={(e) => patch({ docintel_endpoint: e.target.value })}
                />
              </Field>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field
                  label="API key"
                  hint={has.docintel_key ? "A key is saved. Type to replace it." : undefined}
                >
                  <Input
                    type="password"
                    autoComplete="off"
                    placeholder={has.docintel_key ? "•••••••••• (saved)" : ""}
                    value={draft.docintel_key}
                    onChange={(e) => patch({ docintel_key: e.target.value })}
                  />
                </Field>
                <Field label="API version">
                  <Input
                    placeholder="(optional)"
                    value={draft.docintel_api_version}
                    onChange={(e) => patch({ docintel_api_version: e.target.value })}
                  />
                </Field>
              </div>
            </section>

            <Separator />

            {/* Azure Content Understanding */}
            <section className="space-y-3">
              <SectionTitle>Azure Content Understanding</SectionTitle>
              <Field label="Endpoint">
                <Input
                  value={draft.cu_endpoint}
                  onChange={(e) => patch({ cu_endpoint: e.target.value })}
                />
              </Field>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field
                  label="API key"
                  hint={has.cu_key ? "A key is saved. Type to replace it." : undefined}
                >
                  <Input
                    type="password"
                    autoComplete="off"
                    placeholder={has.cu_key ? "•••••••••• (saved)" : ""}
                    value={draft.cu_key}
                    onChange={(e) => patch({ cu_key: e.target.value })}
                  />
                </Field>
                <Field label="Analyzer ID">
                  <Input
                    value={draft.cu_analyzer_id}
                    onChange={(e) => patch({ cu_analyzer_id: e.target.value })}
                  />
                </Field>
              </div>
              <Field
                label="File types"
                hint="Comma-separated extensions, e.g. .pdf, .docx. Empty = all."
              >
                <Input
                  placeholder=".pdf, .docx"
                  value={draft.cu_file_types.join(", ")}
                  onChange={(e) =>
                    patch({
                      cu_file_types: e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </Field>
            </section>

            <Separator />

            {/* Converter knobs */}
            <section className="space-y-3">
              <SectionTitle>Converter options</SectionTitle>
              <Field
                label="ExifTool path"
                hint="Path to exiftool.exe for richer image metadata (optional)."
              >
                <Input
                  value={draft.exiftool_path}
                  onChange={(e) => patch({ exiftool_path: e.target.value })}
                />
              </Field>
              <Field
                label="Word style map"
                hint="Mammoth style map for .docx → Markdown (optional)."
              >
                <Textarea
                  rows={2}
                  value={draft.style_map}
                  onChange={(e) => patch({ style_map: e.target.value })}
                />
              </Field>
            </section>

            <Separator />

            {/* Updates */}
            <section className="space-y-3">
              <SectionTitle>Updates</SectionTitle>
              <Field
                label="App GitHub repository"
                hint="owner/repo — where Omnivert's tagged releases are published. Leave blank to disable app update checks."
              >
                <Input
                  placeholder="your-name/omnivert"
                  value={draft.app_repo}
                  onChange={(e) => patch({ app_repo: e.target.value })}
                />
              </Field>
              <div className="flex items-center justify-between">
                <Label htmlFor="auto_check_updates">Check for updates on launch</Label>
                <Switch
                  id="auto_check_updates"
                  checked={draft.auto_check_updates}
                  onCheckedChange={(v) => patch({ auto_check_updates: v })}
                />
              </div>
            </section>

            <Separator />

            {/* Defaults for new conversions */}
            <section className="space-y-3">
              <SectionTitle>Defaults for new conversions</SectionTitle>
              <div className="space-y-2">
                {(
                  [
                    ["default_enable_plugins", "Enable plugins"],
                    ["default_describe_images", "Describe images with Claude"],
                    ["default_keep_data_uris", "Keep data URIs"],
                  ] as const
                ).map(([key, label]) => (
                  <div key={key} className="flex items-center justify-between">
                    <Label htmlFor={key}>{label}</Label>
                    <Switch
                      id={key}
                      checked={draft[key]}
                      onCheckedChange={(v) => patch({ [key]: v } as Partial<Settings>)}
                    />
                  </div>
                ))}
                <div className="flex items-center justify-between pt-1">
                  <Label>Azure backend</Label>
                  <Select
                    value={draft.default_azure_backend}
                    onValueChange={(v) =>
                      patch({ default_azure_backend: v as AzureBackend })
                    }
                  >
                    <SelectTrigger size="sm" className="w-44">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None (local)</SelectItem>
                      <SelectItem value="docintel">Document Intelligence</SelectItem>
                      <SelectItem value="cu">Content Understanding</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </section>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || loading || !draft}>
            {saving && <Loader2 className="animate-spin" />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
