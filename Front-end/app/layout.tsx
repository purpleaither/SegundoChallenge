import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'GovernancIA | Benefícios sociais no DF',
  description: 'Descubra benefícios sociais disponíveis no Distrito Federal com orientação simples, acolhedora e confiável.',
}

export const viewport: Viewport = {
  colorScheme: 'light',
  themeColor: '#f7f8f5',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  )
}