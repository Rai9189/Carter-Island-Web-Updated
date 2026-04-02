// src/components/layout/Header.tsx
import { ReactNode } from 'react'
import { Anchor } from 'lucide-react'

interface HeaderProps {
  title: string
  subtitle?: string
  emoji?: string 
  children?: ReactNode
}

const Header = ({ title, subtitle,  emoji = "👋", children }: HeaderProps) => {
  // Function untuk mendapatkan tanggal hari ini dalam format yang sesuai
  const getCurrentDate = () => {
    const today = new Date()
    const options: Intl.DateTimeFormatOptions = { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    }
    return today.toLocaleDateString('en-US', options)
  }

  return (
    <div className="bg-white px-6 py-4 lg:px-8">
      <div className="flex items-center justify-between">
        {/* Left side - Welcome message dan date */}
        <div className="ml-16 lg:ml-0">
          {subtitle && (
            <div className="mb-2">
              <h1 className="text-2xl font-bold text-gray-900 flex items-center">
                {subtitle} 
                <span className="text-2xl">{emoji}</span>
              </h1>
              <p className="text-gray-500 text-sm mt-1">
                {getCurrentDate()}
              </p>
            </div>
          )}
          {/* Fallback jika tidak ada subtitle */}
          {!subtitle && (
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
              <p className="text-gray-500 text-sm mt-1">
                {getCurrentDate()}
              </p>
            </div>
          )}
        </div>

        {/* Right side - Logo dan nama web + children */}
        <div className="flex items-center space-x-6">
          {/* Carter Island AUV Logo */}
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-blue-800 rounded-full shadow-sm">
              <Anchor className="h-6 w-6 text-white" />
            </div>
            <div className="text-right">
              <h2 className="text-lg font-bold text-gray-900 leading-tight">Carter Island AUV</h2>
              <p className="text-xs text-gray-500 leading-tight">Underwater Navigation System</p>
            </div>
          </div>

          {/* Vertical divider */}
          {children && <div className="w-px h-8 bg-gray-200"></div>}

          {/* Children (search bar, indicators, etc) */}
          {children && <div className="flex items-center space-x-4">{children}</div>}
        </div>
      </div>
    </div>
  )
}

export default Header