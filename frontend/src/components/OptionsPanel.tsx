import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { AzureBackend, ConvertOptions } from "@/lib/types"

interface Props {
  options: ConvertOptions
  onChange: (patch: Partial<ConvertOptions>) => void
  // Disable knobs that the install can't honor or that need configured keys.
  claudeKeySet: boolean
  azureDocIntelReady: boolean
  azureContentUnderstandingReady: boolean
  // The file tab benefits from extension/charset hints; URL/text less so.
  showHints?: boolean
}

function Toggle({
  id,
  label,
  description,
  checked,
  onCheckedChange,
  disabled,
  disabledHint,
}: {
  id: string
  label: string
  description: string
  checked: boolean
  onCheckedChange: (v: boolean) => void
  disabled?: boolean
  disabledHint?: string
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div className="space-y-0.5">
        <Label htmlFor={id} className={cn(disabled && "opacity-60")}>
          {label}
        </Label>
        <p className="text-xs text-muted-foreground">
          {disabled && disabledHint ? disabledHint : description}
        </p>
      </div>
      <Switch
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
      />
    </div>
  )
}

export function OptionsPanel({
  options,
  onChange,
  claudeKeySet,
  azureDocIntelReady,
  azureContentUnderstandingReady,
  showHints = false,
}: Props) {
  const [hintsOpen, setHintsOpen] = useState(false)

  return (
    <div className="rounded-lg border bg-card/40 p-4">
      <p className="mb-1 text-sm font-medium">Options</p>

      <div className="divide-y divide-border/60">
        <Toggle
          id="opt-plugins"
          label="Enable plugins"
          description="Load installed third-party converter plugins."
          checked={options.enable_plugins}
          onCheckedChange={(v) => onChange({ enable_plugins: v })}
        />
        <Toggle
          id="opt-describe"
          label="Describe images with Claude"
          description="Caption images via the Claude API during conversion."
          checked={options.describe_images}
          onCheckedChange={(v) => onChange({ describe_images: v })}
          disabled={!claudeKeySet}
          disabledHint="Add a Claude API key in Settings to enable image captioning."
        />
        <Toggle
          id="opt-datauris"
          label="Keep data URIs"
          description="Preserve base64 image/data URIs instead of truncating them."
          checked={options.keep_data_uris}
          onCheckedChange={(v) => onChange({ keep_data_uris: v })}
        />

        <div className="flex items-center justify-between gap-4 py-3">
          <div className="space-y-0.5">
            <Label htmlFor="opt-azure">Azure extraction backend</Label>
            <p className="text-xs text-muted-foreground">
              Optional cloud OCR/layout backend (configure in Settings).
            </p>
          </div>
          <Select
            value={options.azure_backend}
            onValueChange={(v) => onChange({ azure_backend: v as AzureBackend })}
          >
            <SelectTrigger id="opt-azure" size="sm" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None (local)</SelectItem>
              <SelectItem value="docintel" disabled={!azureDocIntelReady}>
                Document Intelligence
              </SelectItem>
              <SelectItem value="cu" disabled={!azureContentUnderstandingReady}>
                Content Understanding
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {showHints && (
        <div className="mt-2 border-t border-border/60 pt-2">
          <button
            type="button"
            onClick={() => setHintsOpen((o) => !o)}
            className="flex w-full items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            {hintsOpen ? (
              <ChevronDown className="size-3.5" />
            ) : (
              <ChevronRight className="size-3.5" />
            )}
            Type hints (override auto-detection)
          </button>
          {hintsOpen && (
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="opt-ext" className="text-xs">
                  Extension
                </Label>
                <Input
                  id="opt-ext"
                  placeholder=".pdf"
                  value={options.extension ?? ""}
                  onChange={(e) => onChange({ extension: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="opt-mime" className="text-xs">
                  MIME type
                </Label>
                <Input
                  id="opt-mime"
                  placeholder="application/pdf"
                  value={options.mimetype ?? ""}
                  onChange={(e) => onChange({ mimetype: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="opt-charset" className="text-xs">
                  Charset
                </Label>
                <Input
                  id="opt-charset"
                  placeholder="utf-8"
                  value={options.charset ?? ""}
                  onChange={(e) => onChange({ charset: e.target.value })}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
