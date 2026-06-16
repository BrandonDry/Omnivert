import { Monitor, Moon, Sun } from "lucide-react"

import { Button } from "@/components/ui/button"
import { saveSettings } from "@/lib/api"
import { useTheme, type Theme } from "@/lib/theme"

const ORDER: Theme[] = ["light", "dark", "system"]
const LABEL: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
}

// Cycles light → dark → system. The icon reflects the current mode.
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length]

  function choose(value: Theme) {
    setTheme(value) // instant, local
    // Persist to the backend so the choice survives a reload (where the app
    // re-applies the saved theme). Fire-and-forget — the UI already updated.
    void saveSettings({ theme: value }).catch(() => {})
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => choose(next)}
      title={`Theme: ${LABEL[theme]} (click for ${LABEL[next]})`}
      aria-label={`Theme: ${LABEL[theme]}. Switch to ${LABEL[next]}.`}
    >
      {theme === "light" && <Sun />}
      {theme === "dark" && <Moon />}
      {theme === "system" && <Monitor />}
    </Button>
  )
}
