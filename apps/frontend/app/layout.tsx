import type { Metadata } from 'next'
import { ClientProviders } from '@/components/shared/ClientProviders'
import './globals.css'

export const metadata: Metadata = {
  title: 'AI-Driven Mechanical Design',
  description: 'Design mechanical parts in natural language',
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
