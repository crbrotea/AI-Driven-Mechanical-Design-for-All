import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Locale = 'en' | 'es'
export type Theme = 'light' | 'dark'

type UIStore = {
  locale: Locale
  theme: Theme
  viewerWireframe: boolean
  viewerBackgroundDark: boolean
  formPanelExpanded: boolean
  setLocale: (l: Locale) => void
  toggleTheme: () => void
  setViewerWireframe: (v: boolean) => void
  setViewerBackgroundDark: (v: boolean) => void
  setFormPanelExpanded: (v: boolean) => void
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      locale: 'en',
      theme: 'light',
      viewerWireframe: false,
      viewerBackgroundDark: true,
      formPanelExpanded: true,
      setLocale: (l) => set({ locale: l }),
      toggleTheme: () => set((s) => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),
      setViewerWireframe: (v) => set({ viewerWireframe: v }),
      setViewerBackgroundDark: (v) => set({ viewerBackgroundDark: v }),
      setFormPanelExpanded: (v) => set({ formPanelExpanded: v }),
    }),
    { name: 'mechdesign-ui' },
  ),
)
