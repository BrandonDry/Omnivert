// Light/dark/system theme handling. The chosen mode is mirrored to localStorage so the
// window opens without a flash; the backend `theme` setting is the durable source of
// truth and is pushed here when Settings loads/saves.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

export type Theme = "light" | "dark" | "system"

const STORAGE_KEY = "omnivert-theme"

interface ThemeContextValue {
  theme: Theme
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
}

function applyTheme(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && systemPrefersDark())
  document.documentElement.classList.toggle("dark", dark)
}

function readStored(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system"
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStored)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  // Track OS changes while in "system" mode.
  useEffect(() => {
    if (theme !== "system") return
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const onChange = () => applyTheme("system")
    mq.addEventListener("change", onChange)
    return () => mq.removeEventListener("change", onChange)
  }, [theme])

  const setTheme = useCallback((next: Theme) => {
    localStorage.setItem(STORAGE_KEY, next)
    setThemeState(next)
  }, [])

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider")
  return ctx
}
