'use client'
import { useEffect, useState } from 'react'
import { useStore } from '@/store/useStore'
import LoginPage from '@/components/LoginPage'
import DashboardPage from '@/components/DashboardPage'
import Header from '@/components/Header'

export default function Home() {
  const { user, token, fetchDashboard } = useStore()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const t = localStorage.getItem('auth_token')
    if (t) {
      fetchDashboard()
    }
    setReady(true)
  }, [])

  if (!ready) return <div className="flex items-center justify-center min-h-screen"><div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" /></div>

  if (!user || !token) return <LoginPage />

  return (
    <div className="min-h-screen bg-dark-500">
      <Header />
      <DashboardPage />
    </div>
  )
}
