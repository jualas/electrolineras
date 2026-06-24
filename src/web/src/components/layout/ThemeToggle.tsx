import type { ThemeMode } from '../../hooks/useTheme'

type ThemeToggleProps = {
  theme: ThemeMode
  onToggle: () => void
}

export function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={onToggle}
      aria-label={theme === 'dark' ? 'Activar tema claro' : 'Activar tema oscuro'}
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  )
}
