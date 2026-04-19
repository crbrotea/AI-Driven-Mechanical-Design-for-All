import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from './uiStore'

describe('uiStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useUIStore.setState({
      locale: 'en',
      theme: 'light',
      viewerWireframe: false,
      viewerBackgroundDark: true,
      formPanelExpanded: true,
    })
  })

  it('defaults to en locale and light theme', () => {
    const { locale, theme } = useUIStore.getState()
    expect(locale).toBe('en')
    expect(theme).toBe('light')
  })

  it('setLocale updates state', () => {
    useUIStore.getState().setLocale('es')
    expect(useUIStore.getState().locale).toBe('es')
  })

  it('toggleTheme flips light/dark', () => {
    useUIStore.getState().toggleTheme()
    expect(useUIStore.getState().theme).toBe('dark')
    useUIStore.getState().toggleTheme()
    expect(useUIStore.getState().theme).toBe('light')
  })

  it('viewer toggles work', () => {
    const { setViewerWireframe } = useUIStore.getState()
    setViewerWireframe(true)
    expect(useUIStore.getState().viewerWireframe).toBe(true)
  })
})
