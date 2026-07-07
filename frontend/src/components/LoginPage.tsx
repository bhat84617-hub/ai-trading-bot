'use client'
import { useState } from 'react'
import { api } from '@/lib/api'
import { useStore } from '@/store/useStore'
import { BarChart3, Eye, EyeOff, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const { setUser, fetchDashboard } = useStore()
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = isLogin ? await api.login(email, password) : await api.signup(email, password, name)
      setUser(res.user, res.access_token)
      await fetchDashboard()
    } catch (err: any) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-500 p-5">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <BarChart3 className="mx-auto text-accent mb-4" size={40} />
          <h1 className="text-2xl font-bold">AI Trading Bot</h1>
          <p className="text-gray-500 text-sm mt-2">Algorithmic trading powered by artificial intelligence</p>
        </div>

        <div className="card p-8">
          <div className="flex gap-2 mb-6 bg-dark-700 rounded-xl p-1">
            <button onClick={() => setIsLogin(true)} className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${isLogin ? 'bg-accent text-white' : 'text-gray-400 hover:text-white'}`}>Login</button>
            <button onClick={() => setIsLogin(false)} className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${!isLogin ? 'bg-accent text-white' : 'text-gray-400 hover:text-white'}`}>Sign Up</button>
          </div>

          <form onSubmit={handleSubmit}>
            {!isLogin && (
              <div className="mb-4">
                <label className="text-xs text-gray-400 mb-1 block">Full Name</label>
                <input value={name} onChange={e => setName(e.target.value)} className="w-full px-4 py-2.5 bg-dark-700 border border-white/5 rounded-xl text-sm text-white outline-none focus:border-accent/50 transition-colors" placeholder="John Doe" />
              </div>
            )}
            <div className="mb-4">
              <label className="text-xs text-gray-400 mb-1 block">Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} className="w-full px-4 py-2.5 bg-dark-700 border border-white/5 rounded-xl text-sm text-white outline-none focus:border-accent/50 transition-colors" placeholder="you@example.com" required />
            </div>
            <div className="mb-6">
              <label className="text-xs text-gray-400 mb-1 block">Password</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} className="w-full px-4 py-2.5 bg-dark-700 border border-white/5 rounded-xl text-sm text-white outline-none focus:border-accent/50 transition-colors pr-10" placeholder="••••••••" required />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"><EyeOff size={16} /></button>
              </div>
            </div>

            {error && <p className="text-red-400 text-xs mb-4">{error}</p>}

            <button type="submit" disabled={loading} className="w-full py-2.5 bg-accent hover:bg-accent/90 text-white rounded-xl font-medium text-sm transition-all flex items-center justify-center gap-2">
              {loading ? <Loader2 className="animate-spin" size={16} /> : null}
              {isLogin ? 'Login' : 'Create Account'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-600 mt-6">Paper trading mode • No real funds at risk</p>
      </div>
    </div>
  )
}
