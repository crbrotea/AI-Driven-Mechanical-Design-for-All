import createMiddleware from 'next-intl/middleware'
import { LOCALES, DEFAULT_LOCALE } from '@/lib/intl/config'

export default createMiddleware({
  locales: LOCALES,
  defaultLocale: DEFAULT_LOCALE,
  localePrefix: 'never',
})

export const config = {
  matcher: ['/((?!api|_next|.*\\..*).*)'],
}
