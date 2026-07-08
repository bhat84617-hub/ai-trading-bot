'use client'
import { useStore } from '@/store/useStore'
import { LineChart, LogOut, User, ChevronDown, Check, Flame, AlertTriangle } from 'lucide-react'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

// Bug fix: this list used to include 'oanda' and standalone 'alpaca' as if
// they were switchable ccxt crypto exchanges. They aren't — Alpaca is now
// wired automatically for every stock symbol (no switching needed), and
// OANDA was never actually implemented. This list only shows brokers that
// are real and switchable: crypto exchanges (ccxt) + India-specific
// overrides (Dhan/OctaFX).
const CRYPTO_BROKERS = ['bybit', 'binance', 'okx', 'kucoin', 'kraken', 'coinbase', 'gateio', 'bitget', 'mexc']

function RiskyModePill() {
  const [status, setStatus] = useState<any>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [duration, setDuration] = useState(240)

  const load = () => api.getRiskyMode().then(setStatus).catch(() => {})
  useEffect(() => { load() }, [])

  const toggle = async (enable: boolean) => {
    setBusy(true)
    try {
      const res = await api.setRiskyMode({ enabled: enable, duration_minutes: duration })
      setStatus(res)
      if (enable) setOpen(false)
    } catch (e) { console.error(e) } finally { setBusy(false) }
  }

  const isOn = !!status?.enabled
  const minutesLeft = status?.expires_at ? Math.max(0, Math.round((new Date(status.expires_at).getTime() - Date.now()) / 60000)) : 0

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className={`flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded-full transition-colors ${isOn ? 'bg-bad text-white' : 'bg-black/5 text-ink-500 hover:text-ink-900 hover:bg-black/10'}`}>
        <Flame size={11} />
        <span className="font-medium">{isOn ? `Risky · ${minutesLeft}m` : 'Risky Mode'}</span>
      </button>
      {open && (
        <div className="absolute top-9 left-0 w-72 card !rounded-2xl p-4 shadow-xl z-50">
          <div className="flex items-start gap-2 mb-3">
            <AlertTriangle size={14} className="text-bad mt-0.5 shrink-0" />
            <p className="text-[11px] text-ink-500 leading-relaxed">
              Loosens confidence/R:R/position-size minimums so more signals qualify. Daily-loss and drawdown limits still apply — just raised (capped at 25% / 40%, never removed). Auto-expires so it can't be left on by accident.
            </p>
          </div>
          {status && (
            <div className="grid grid-cols-2 gap-2 text-[11px] mb-3 text-ink-500">
              <div className="bg-black/5 rounded-lg px-2 py-1.5">Min confidence: <b className="text-ink-900">{status.min_confidence_score}%</b></div>
              <div className="bg-black/5 rounded-lg px-2 py-1.5">Min R:R: <b className="text-ink-900">1:{status.min_risk_reward}</b></div>
              <div className="bg-black/5 rounded-lg px-2 py-1.5">Max daily loss: <b className="text-ink-900">{status.max_daily_loss}%</b></div>
              <div className="bg-black/5 rounded-lg px-2 py-1.5">Max drawdown: <b className="text-ink-900">{status.max_drawdown}%</b></div>
            </div>
          )}
          {isOn ? (
            <button disabled={busy} onClick={() => toggle(false)} className="w-full py-2 rounded-xl bg-black/5 hover:bg-black/10 text-ink-900 text-xs font-medium">Turn off now</button>
          ) : (
            <>
              <label className="text-[11px] text-ink-300 block mb-1">Duration</label>
              <select value={duration} onChange={e => setDuration(Number(e.target.value))} className="w-full mb-3 px-3 py-2 glass-input rounded-lg text-xs text-ink-900 outline-none">
                <option value={60}>1 hour</option>
                <option value={240}>4 hours</option>
                <option value={720}>12 hours</option>
                <option value={1440}>24 hours (max)</option>
              </select>
              <button disabled={busy} onClick={() => toggle(true)} className="w-full py-2 rounded-xl bg-bad hover:opacity-90 text-white text-xs font-medium">Enable Risky Mode</button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function Header() {
  const { user, logout, fetchDashboard } = useStore()
  const [showMenu, setShowMenu] = useState(false)
  const [showBroker, setShowBroker] = useState(false)
  const [cryptoBroker, setCryptoBroker] = useState('bybit')
  const [switching, setSwitching] = useState(false)

  useEffect(() => {
    api.getBrokers().then((res: any) => {
      if (res?.crypto_broker) setCryptoBroker(res.crypto_broker)
    }).catch(() => {})
  }, [])

  const switchBroker = async (id: string) => {
    setSwitching(true)
    try {
      // Bug fix: previously this only did localStorage.setItem and never
      // actually told the backend — switching broker in the UI silently did
      // nothing. Now it calls the real endpoint.
      await api.switchBroker(id)
      setCryptoBroker(id)
    } catch (e) {
      console.error('Broker switch failed', e)
    } finally {
      setSwitching(false)
      setShowBroker(false)
    }
  }

  const modeStyle = user?.trade_mode === 'live'
    ? 'bg-bad-bg text-bad'
    : 'bg-good-bg text-good'

  return (
    <header className="spatial-shell sticky top-3 z-50 mx-3 mt-3 rounded-3xl">
      <div className="max-w-7xl mx-auto px-5 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl glass flex items-center justify-center">
            <LineChart className="text-accent" size={16} />
          </div>
          <span className="font-display font-bold text-sm text-ink-900 hidden sm:inline">AI Trading Bot</span>

          {/* Crypto broker selector — stocks always go through Alpaca automatically */}
          <div className="relative">
            <button onClick={() => setShowBroker(!showBroker)} className="flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded-full bg-black/5 hover:bg-black/10 text-ink-500 hover:text-ink-900 transition-colors">
              <span className="w-1.5 h-1.5 rounded-full bg-good"></span>
              <span className="uppercase font-medium">{cryptoBroker}</span>
              <ChevronDown size={10} />
            </button>
            {showBroker && (
              <div className="absolute top-9 left-0 w-52 card !rounded-2xl p-2 shadow-xl z-50">
                <p className="text-[10px] text-ink-300 px-2 pb-1 font-semibold uppercase tracking-wider">Crypto exchange (Bybit-ready)</p>
                {CRYPTO_BROKERS.map(b => (
                  <button key={b} disabled={switching} onClick={() => switchBroker(b)} className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs transition-colors ${cryptoBroker === b ? 'bg-accent/15 text-accent font-medium' : 'text-ink-500 hover:text-ink-900 hover:bg-black/5'}`}>
                    <span className="capitalize">{b}</span>
                    {cryptoBroker === b && <Check size={12} />}
                  </button>
                ))}
                <p className="text-[10px] text-ink-300 px-2 pb-1 pt-2 font-semibold uppercase tracking-wider">Stocks</p>
                <div className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs text-ink-500">
                  <span>Alpaca (auto)</span>
                  <Check size={12} className="text-good" />
                </div>
                <p className="text-[10px] text-ink-300 px-2 pb-1 pt-2 font-semibold uppercase tracking-wider">India override</p>
                {['dhan', 'octafx'].map(b => (
                  <button key={b} disabled={switching} onClick={() => switchBroker(b)} className="w-full flex items-center px-3 py-1.5 rounded-lg text-xs text-ink-500 hover:text-ink-900 hover:bg-black/5 capitalize">{b}</button>
                ))}
              </div>
            )}
          </div>

          <span className={`text-[10px] px-2.5 py-1 rounded-full font-medium uppercase tracking-wide ${modeStyle}`}>
            {user?.trade_mode || 'paper'}
          </span>
          <RiskyModePill />
        </div>
        <div className="relative">
          <button onClick={() => setShowMenu(!showMenu)} className="flex items-center gap-2 text-sm text-ink-500 hover:text-ink-900 transition-colors">
            <div className="w-7 h-7 rounded-full bg-accent/15 flex items-center justify-center"><User size={13} className="text-accent" /></div>
            <span className="hidden sm:inline">{user?.email?.split('@')[0]}</span>
          </button>
          {showMenu && (
            <div className="absolute right-0 top-10 w-44 card !rounded-2xl p-2 shadow-xl">
              <button onClick={() => { fetchDashboard(); setShowMenu(false) }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-500 hover:text-ink-900 hover:bg-black/5 rounded-lg transition-colors">
                <LineChart size={14} /> Refresh
              </button>
              <button onClick={() => { logout(); setShowMenu(false) }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-bad hover:bg-black/5 rounded-lg transition-colors">
                <LogOut size={14} /> Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
