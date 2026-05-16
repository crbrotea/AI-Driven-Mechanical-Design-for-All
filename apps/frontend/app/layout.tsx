import type { Metadata, Viewport } from 'next'
import { ClientProviders } from '@/components/shared/ClientProviders'
import './globals.css'

export const metadata: Metadata = {
  title: 'AI-Driven Mechanical Design',
  description: 'Design mechanical parts in natural language',
  icons: {
    icon: '/logo.png',
    apple: '/logo.png',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ClientProviders>{children}</ClientProviders>
      </body>
    </html>
  )
}
