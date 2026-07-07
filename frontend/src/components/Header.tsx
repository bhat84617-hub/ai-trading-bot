'use client'
import { useStore } from '@/store/useStore'
import { BarChart3, LogOut, User, Settings, ChevronDown } from 'lucide-react'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

const BROKER_LIST = [
  { id: 'binance', label: 'Binance', type: 'crypto' },
  { id: 'bybit', label: 'Bybit', type: 'crypto' },
  { id: 'okx', label: 'OKX', type: 'crypto' },
  { id: 'kucoin', label: 'KuCoin', type: 'crypto' },
  { id: 'kraken', label: 'Kraken', type: 'crypto' },
  { id: 'coinbase', label: 'Coinbase', type: 'crypto' },
  { id: 'gateio', label: 'Gate.io', type: 'crypto' },
  { id: 'bitget', label: 'Bitget', type: 'crypto' },
  { id: 'mexc', label: 'MEXC', type: 'crypto' },
  { id: 'coindcx', label: 'CoinDCX', type: 'crypto' },
  { id: 'alpaca', label: 'Alpaca', type: 'stocks' },
  { id: 'dhan', label: 'Dhan (India)', type: 'stocks' },
  { id: 'oanda', label: 'OANDA', type: 'forex' },
  { id: 'octafx', label: 'OctaFX', type: 'forex' },
]

export default function Header() {
  const { user, logout, fetchDashboard } = useStore()
  const [showMenu, setShowMenu] = useState(false)
  const [showBroker, setShowBroker] = useState(false)
  const [broker, setBroker] = useState('binance')

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setBroker(localStorage.getItem('broker_name') || 'binance')
    }
  }, [])

  const switchBroker = async (id: string) => {
    setBroker(id)
    localStorage.setItem('broker_name', id)
    setShowBroker(false)
  }

  return (
    <header className="glass border-b border-white/5 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-5 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BarChart3 className="text-accent" size={20} />
          <span className="font-bold text-sm">AI Trading Bot</span>

          {/* Broker Selector */}
          <div className="relative">
            <button onClick={() => setShowBroker(!showBroker)} className="flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors">
              <span className="uppercase">{broker}</span>
              <ChevronDown size={10} />
            </button>
            {showBroker && (
              <div className="absolute top-6 left-0 w-48 glass rounded-xl p-2 shadow-xl max-h-72 overflow-y-auto z-50">
                <p className="text-[10px] text-gray-500 px-2 pb-1 font-semibold uppercase tracking-wider">🌍 International Crypto</p>
                {BROKER_LIST.filter(b => b.type === 'crypto' && b.id !== 'coindcx').map(b => (
                  <button key={b.id} onClick={() => switchBroker(b.id)} className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors ${broker === b.id ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>{b.label}</button>
                ))}
                <p className="text-[10px] text-gray-500 px-2 pb-1 pt-2 font-semibold uppercase tracking-wider">🇮🇳 India</p>
                <button onClick={() => switchBroker('coindcx')} className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors ${broker === 'coindcx' ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>CoinDCX (Crypto)</button>
                <button onClick={() => switchBroker('dhan')} className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors ${broker === 'dhan' ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>Dhan (Stocks)</button>
                <p className="text-[10px] text-gray-500 px-2 pb-1 pt-2 font-semibold uppercase tracking-wider">💱 Forex</p>
                {BROKER_LIST.filter(b => b.type === 'forex').map(b => (
                  <button key={b.id} onClick={() => switchBroker(b.id)} className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors ${broker === b.id ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>{b.label}</button>
                ))}
                <p className="text-[10px] text-gray-500 px-2 pb-1 pt-2 font-semibold uppercase tracking-wider">🇺🇸 US Stocks</p>
                {BROKER_LIST.filter(b => b.type === 'stocks' && b.id !== 'dhan').map(b => (
                  <button key={b.id} onClick={() => switchBroker(b.id)} className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors ${broker === b.id ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>{b.label}</button>
                ))}
              </div>
            )}
          </div>

          <span className={`text-[10px] px-2 py-0.5 rounded-full ${user?.trade_mode === 'live' ? 'bg-green-500/20 text-green-400' : user?.trade_mode === 'approval' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'}`}>
            {user?.trade_mode || 'paper'}
          </span>
        </div>
        <div className="relative">
          <button onClick={() => setShowMenu(!showMenu)} className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
            <User size={16} />
            {user?.email?.split('@')[0]}
          </button>
          {showMenu && (
            <div className="absolute right-0 top-8 w-48 glass rounded-xl p-2 shadow-xl">
              <button onClick={() => { fetchDashboard(); setShowMenu(false) }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                <BarChart3 size={14} /> Dashboard
              </button>
              <button onClick={() => { logout(); setShowMenu(false) }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-white/5 rounded-lg transition-colors">
                <LogOut size={14} /> Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
