// src/components/ui/MapButton.tsx
'use client'

import { Button } from '@/components/ui/button'

interface MapButtonProps {
  lat: number
  lng: number
  className?: string
  children?: React.ReactNode
}

export default function MapButton({ lat, lng, className, children }: MapButtonProps) {
  const handleClick = () => {
    window.open(`https://www.google.com/maps?q=${lat},${lng}&z=15`, '_blank')
  }

  return (
    <Button 
      variant="outline" 
      className={className || "w-full"} 
      size="sm"
      onClick={handleClick}
    >
      {children || "View Full Map"}
    </Button>
  )
}