import { getRequestConfig } from 'next-intl/server'
import { notFound } from 'next/navigation'

export const LOCALES = ['en', 'es'] as const
export type Locale = (typeof LOCALES)[number]
export const DEFAULT_LOCALE: Locale = 'en'

export default getRequestConfig(async ({ locale }) => {
  if (!LOCALES.includes(locale as Locale)) notFound()
  return { messages: (await import(`@/messages/${locale}.json`)).default }
})
