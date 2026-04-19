import type { Metadata } from 'next'
import { getLocale } from 'next-intl/server'
import './globals.css'

export const metadata: Metadata = {
  title: 'AI-Driven Mechanical Design',
  description: 'Design mechanical parts in natural language',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale()
  return (
    <html lang={locale}>
      <body>{children}</body>
    </html>
  )
}
