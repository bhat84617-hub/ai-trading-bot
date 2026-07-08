import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Trading Bot',
  description: 'AI-powered algorithmic trading bot with real-time market analysis',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  )
}
