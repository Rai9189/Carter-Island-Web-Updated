import ToasterProvider from '@/components/providers/ToasterProvider'
import './globals.css'

export const metadata = {
  title: 'Carter Island AUV Dashboard',
  description: 'Autonomous Underwater Vehicle Control System',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50">
        {children}
        <ToasterProvider />
      </body>
    </html>
  )
}