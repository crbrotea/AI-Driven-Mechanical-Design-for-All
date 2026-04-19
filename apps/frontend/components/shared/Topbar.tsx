'use client'
import { useTranslations } from 'next-intl'
import { useUIStore } from '@/lib/stores/uiStore'
import { Button } from '@/components/ui/button'

export function Topbar() {
  const t = useTranslations('topbar')
  const locale = useUIStore((s) => s.locale)
  const setLocale = useUIStore((s) => s.setLocale)
  const toggleTheme = useUIStore((s) => s.toggleTheme)

  return (
    <header role="banner" className="flex items-center justify-between border-b border-border px-4 py-2">
      <div className="font-semibold">MechDesign AI</div>
      <nav className="flex gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setLocale(locale === 'en' ? 'es' : 'en')}
          aria-label={t('locale_toggle', { locale: locale === 'en' ? 'ES' : 'EN' })}
        >
          {locale === 'en' ? 'ES' : 'EN'}
        </Button>
        <Button variant="ghost" size="sm" onClick={toggleTheme} aria-label={t('theme_toggle')}>
          🌓
        </Button>
      </nav>
    </header>
  )
}
