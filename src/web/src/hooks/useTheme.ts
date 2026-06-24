import { useCallback, useEffect, useState } from 'react'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'electrolineras-theme'

function readStoredTheme(): ThemeMode | null {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') {
    return stored
  }
  return null
}

function systemTheme(): ThemeMode {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: ThemeMode) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeMode>(() => readStoredTheme() ?? systemTheme())

  useEffect(() => {
    applyTheme(theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setThemeState((current) => (current === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggleTheme }
}
