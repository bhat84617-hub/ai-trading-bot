'use client'
import { useState } from 'react'
import { api } from '@/lib/api'
import { useStore } from '@/store/useStore'
import { LineChart, Eye, EyeOff, Loader2 } from 'lucide-react'

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
    <div className="min-h-screen flex items-center justify-center p-5">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl glass mb-4 animate-pulse-glow">
            <LineChart className="text-accent" size={26} />
          </div>
          <h1 className="font-display text-3xl font-bold text-ink-900">AI Trading Bot</h1>
          <p className="text-ink-300 text-sm mt-2">Real analysis. Real brokers. Real trades.</p>
        </div>

        <div className="spatial-shell rounded-3xl p-2">
          <div className="card !rounded-2xl p-8">
            <div className="flex gap-2 mb-6 bg-black/5 rounded-xl p-1">
              <button onClick={() => setIsLogin(true)} className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${isLogin ? 'bg-accent text-white shadow-sm' : 'text-ink-300 hover:text-ink-900'}`}>Login</button>
              <button onClick={() => setIsLogin(false)} className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${!isLogin ? 'bg-accent text-white shadow-sm' : 'text-ink-300 hover:text-ink-900'}`}>Sign Up</button>
            </div>

            <form onSubmit={handleSubmit}>
              {!isLogin && (
                <div className="mb-4">
                  <label className="text-xs text-ink-300 mb-1 block">Full Name</label>
                  <input value={name} onChange={e => setName(e.target.value)} className="w-full px-4 py-2.5 glass-input rounded-xl text-sm text-ink-900 outline-none focus:border-accent/50 transition-colors" placeholder="John Doe" />
                </div>
              )}
              <div className="mb-4">
                <label className="text-xs text-ink-300 mb-1 block">Email</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} className="w-full px-4 py-2.5 glass-input rounded-xl text-sm text-ink-900 outline-none focus:border-accent/50 transition-colors" placeholder="you@example.com" required />
              </div>
              <div className="mb-6">
                <label className="text-xs text-ink-300 mb-1 block">Password</label>
                <div className="relative">
                  <input type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} className="w-full px-4 py-2.5 glass-input rounded-xl text-sm text-ink-900 outline-none focus:border-accent/50 transition-colors pr-10" placeholder="••••••••" required />
                  <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-300 hover:text-ink-700">{showPw ? <Eye size={16} /> : <EyeOff size={16} />}</button>
                </div>
              </div>

              {error && <p className="text-bad text-xs mb-4">{error}</p>}

              <button type="submit" disabled={loading} className="w-full py-2.5 bg-accent hover:bg-accent-600 text-white rounded-xl font-medium text-sm transition-all flex items-center justify-center gap-2 shadow-md shadow-accent/20">
                {loading ? <Loader2 className="animate-spin" size={16} /> : null}
                {isLogin ? 'Login' : 'Create Account'}
              </button>
            </form>
          </div>
        </div>

        <p className="text-center text-xs text-ink-300 mt-6">Defaults to paper trading — flip TRADE_MODE=live in .env when you're ready</p>
      </div>
    </div>
  )
}
