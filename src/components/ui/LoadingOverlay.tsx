// src/components/ui/LoadingOverlay.tsx (Glass Morphism - Gray Terang)
'use client'

interface LoadingOverlayProps {
  isVisible: boolean
  message?: string
  showDots?: boolean
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export default function LoadingOverlay({ 
  isVisible, 
  message = "Loading", 
  showDots = true,
  size = 'md',
  className = '' 
}: LoadingOverlayProps) {
  if (!isVisible) return null

  const sizeClasses = {
    sm: 'h-6 w-6',
    md: 'h-8 w-8', 
    lg: 'h-10 w-10'
  }

  const spinnerSize = sizeClasses[size]

  return (
    <div className={`fixed inset-0 z-50 bg-slate-200/30 backdrop-blur-md flex items-center justify-center ${className}`}>
      {/* Glass morphism card dengan warna lebih terang */}
      <div className="bg-white/40 backdrop-blur-lg rounded-2xl p-6 shadow-xl border border-white/50 flex flex-col items-center">
        {/* Elegant spinner dengan warna lebih terang */}
        <div className="relative mb-3">
          <div className={`${spinnerSize} rounded-full border-2 border-slate-200/50`}></div>
          <div className={`absolute inset-0 ${spinnerSize} rounded-full border-2 border-transparent border-t-slate-400 animate-spin`}></div>
        </div>
        
        {/* Text dengan warna yang lebih soft */}
        <div className="text-slate-600 font-medium text-sm flex items-center">
          {message}
          {showDots && (
            <span className="ml-1 flex">
              <span className="animate-bounce mx-0.5 h-1 w-1 bg-slate-400 rounded-full" style={{animationDelay: '0ms'}}></span>
              <span className="animate-bounce mx-0.5 h-1 w-1 bg-slate-400 rounded-full" style={{animationDelay: '150ms'}}></span>
              <span className="animate-bounce mx-0.5 h-1 w-1 bg-slate-400 rounded-full" style={{animationDelay: '300ms'}}></span>
            </span>
          )}
        </div>
      </div>
    </div>
  )
}