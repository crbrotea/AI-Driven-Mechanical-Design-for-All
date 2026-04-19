'use client'
import { NextIntlClientProvider } from 'next-intl'
import type { AbstractIntlMessages } from 'next-intl'
import { useEffect, useState } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'
import enMessages from '@/messages/en.json'

export function ClientProviders({ children }: { children: React.ReactNode }) {
  const locale = useUIStore((s) => s.locale)
  const theme = useUIStore((s) => s.theme)
  const [messages, setMessages] = useState<AbstractIntlMessages>(enMessages)

  useEffect(() => {
    import(`@/messages/${locale}.json`).then((mod) => setMessages(mod.default))
  }, [locale])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      {children}
    </NextIntlClientProvider>
  )
}
