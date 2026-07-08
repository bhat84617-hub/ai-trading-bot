'use client'
import { useEffect, useState, useCallback } from 'react'
import { useStore } from '@/store/useStore'
import { api } from '@/lib/api'
import { BarChart3, TrendingUp, Activity, DollarSign, RefreshCw, Play, XCircle, Loader2, Eye, Zap, Plus, Trash2, Sparkles, CandlestickChart } from 'lucide-react'
import TradeChart from './TradeChart'

export default function DashboardPage() {
  const { dashboard, fetchDashboard } = useStore()
  const [signals, setSignals] = useState<any[]>([])
  const [trades, setTrades] = useState<any[]>([])
  const [watchlist, setWatchlist] = useState<any[]>([])
  const [newSymbol, setNewSymbol] = useState('')
  const [addingSymbol, setAddingSymbol] = useState(false)
  const [activeTab, setActiveTab] = useState<'overview' | 'watchlist' | 'signals' | 'trades' | 'analysis'>('watchlist')
  const [scanning, setScanning] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisSymbol, setAnalysisSymbol] = useState('')
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const [chartSymbol, setChartSymbol] = useState<string | null>(null)
  const [chartTrade, setChartTrade] = useState<any>(null)

  const loadData = useCallback(async () => {
    try {
      const [s, t, w] = await Promise.all([api.getSignals(10), api.getTrades(10), api.getWatchlist()])
      setSignals(s); setTrades(t); setWatchlist(w)
    } catch (e) { console.error(e) }
  }, [])

  useEffect(() => { fetchDashboard(); loadData() }, [])

  const handleAddSymbol = async () => {
    if (!newSymbol.trim()) return
    setAddingSymbol(true)
    try {
      await api.addToWatchlist(newSymbol.trim().toUpperCase())
      setNewSymbol('')
      await loadData()
    } catch (e) { console.error(e) }
    setAddingSymbol(false)
  }

  const handleRemoveSymbol = async (id: string) => {
    try { await api.removeFromWatchlist(id); await loadData() } catch (e) { console.error(e) }
  }

  const handleScan = async () => {
    setScanning(true)
    try {
      const res = await api.scan()
      setSignals(res.signals || [])
      await fetchDashboard()
    } catch (e) { console.error(e) }
    setScanning(false)
  }

  const handleApprove = async (id: string, action: 'approve' | 'reject') => {
    try { await api.approveSignal(id, action); await loadData(); await fetchDashboard() } catch (e) { console.error(e) }
  }

  const handleCloseTrade = async (id: string) => {
    try { await api.closeTrade(id); await loadData(); await fetchDashboard() } catch (e) { console.error(e) }
  }

  const handleAnalyze = async () => {
    if (!analysisSymbol) return
    setAnalyzing(true)
    try { setAnalysisResult(await api.aiAnalyze(analysisSymbol.toUpperCase())) } catch (e: any) { console.error(e) }
    setAnalyzing(false)
  }

  const statCards = [
    { label: 'Total PnL', value: `$${dashboard?.total_pnl?.toFixed(2) || '0.00'}`, icon: DollarSign, positive: (dashboard?.total_pnl ?? 0) >= 0 },
    { label: 'Daily PnL', value: `$${dashboard?.daily_pnl?.toFixed(2) || '0.00'}`, icon: TrendingUp, positive: (dashboard?.daily_pnl ?? 0) >= 0 },
    { label: 'Win Rate', value: `${dashboard?.win_rate || 0}%`, icon: Activity, positive: true },
    { label: 'Open Positions', value: dashboard?.open_positions || 0, icon: BarChart3, positive: true },
    { label: 'Total Trades', value: dashboard?.total_trades || 0, icon: RefreshCw, positive: true },
    { label: 'Portfolio', value: `$${(dashboard?.portfolio_value || 0).toLocaleString()}`, icon: DollarSign, positive: true },
  ]

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-5 py-6">
      <div className="spatial-shell rounded-3xl p-4 sm:p-6">

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
          {statCards.map((s, i) => (
            <div key={i} className="card p-4 animate-slide-up" style={{ animationDelay: `${i * 40}ms` }}>
              <s.icon size={16} className={s.positive ? 'text-good' : 'text-bad'} />
              <p className="text-lg font-bold mt-2 text-ink-900">{s.value}</p>
              <p className="text-xs text-ink-300">{s.label}</p>
            </div>
          ))}
        </div>

        <div className="flex gap-2 mb-6 overflow-x-auto">
          {(['watchlist', 'overview', 'signals', 'trades', 'analysis'] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${activeTab === tab ? 'bg-accent text-white shadow-sm' : 'bg-black/5 text-ink-500 hover:text-ink-900'}`}>
              {tab === 'watchlist' ? '⭐ Watchlist' : tab === 'overview' ? '📊 Overview' : tab === 'signals' ? '🎯 Signals' : tab === 'trades' ? '📈 Trades' : '🤖 Deep Analysis'}
            </button>
          ))}
          <button onClick={handleScan} disabled={scanning} className="px-4 py-2 rounded-xl text-sm font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-all ml-auto flex items-center gap-2 whitespace-nowrap">
            {scanning ? <Loader2 className="animate-spin" size={14} /> : <Zap size={14} />} Scan Now
          </button>
        </div>

        {activeTab === 'watchlist' && (
          <div>
            <div className="card p-5 mb-5">
              <div className="flex items-center gap-2 mb-1">
                <Sparkles size={15} className="text-accent" />
                <h3 className="font-semibold text-ink-900 text-sm">Add a symbol — the bot does the rest</h3>
              </div>
              <p className="text-xs text-ink-300 mb-4">Stocks (TSLA, AAPL...) route to Alpaca automatically. Crypto pairs (BTC/USDT...) route to your selected exchange.</p>
              <div className="flex gap-3">
                <input value={newSymbol} onChange={e => setNewSymbol(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleAddSymbol()}
                  placeholder="e.g. TSLA, AAPL, BTC/USDT" className="flex-1 px-4 py-2.5 glass-input rounded-xl text-sm text-ink-900 outline-none focus:border-accent/50" />
                <button onClick={handleAddSymbol} disabled={addingSymbol} className="px-5 py-2.5 bg-accent hover:bg-accent-600 text-white rounded-xl text-sm font-medium flex items-center gap-2">
                  {addingSymbol ? <Loader2 className="animate-spin" size={14} /> : <Plus size={14} />} Add
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {watchlist.length === 0 && <p className="text-ink-300 text-sm text-center py-8">Watchlist empty — add a symbol above, then hit Scan Now.</p>}
              {watchlist.map((w: any) => (
                <div key={w.id} className="card p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-9 h-9 rounded-xl bg-accent/10 flex items-center justify-center text-xs font-bold text-accent">{w.symbol.replace('/', '').slice(0, 2)}</span>
                    <div><p className="text-sm font-medium text-ink-900">{w.symbol}</p><p className="text-xs text-ink-300">{w.timeframe}</p></div>
                  </div>
                  <button onClick={() => handleRemoveSymbol(w.id)} className="p-2 rounded-lg text-ink-300 hover:text-bad hover:bg-bad-bg transition-colors"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'overview' && (
          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold text-ink-500 mb-3">Recent Signals</h3>
              <div className="space-y-2">
                {(dashboard?.recent_signals || signals).slice(0, 5).map((s: any) => (
                  <div key={s.id} className="card p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${s.direction === 'long' ? 'bg-good-bg text-good' : 'bg-bad-bg text-bad'}`}>{s.direction === 'long' ? 'L' : 'S'}</span>
                      <div><p className="text-sm font-medium text-ink-900">{s.symbol}</p><p className="text-xs text-ink-300">{(s.reason || '').slice(0, 50)}</p></div>
                    </div>
                    <span className={`text-xs font-semibold ${s.confidence_score >= 70 ? 'text-good' : 'text-amber-600'}`}>{s.confidence_score}%</span>
                  </div>
                ))}
                {(!dashboard?.recent_signals || dashboard.recent_signals.length === 0) && signals.length === 0 && <p className="text-ink-300 text-sm text-center py-8">No signals yet. Click Scan Now.</p>}
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-ink-500 mb-3">Recent Trades</h3>
              <div className="space-y-2">
                {(dashboard?.recent_trades || trades).slice(0, 5).map((t: any) => (
                  <div key={t.id} className="card p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${t.direction === 'long' ? 'bg-good-bg text-good' : 'bg-bad-bg text-bad'}`}>{t.direction === 'long' ? 'L' : 'S'}</span>
                      <div><p className="text-sm font-medium text-ink-900">{t.symbol}</p><p className="text-xs text-ink-300">{t.status}</p></div>
                    </div>
                    <span className={`text-sm font-bold ${(t.pnl || 0) >= 0 ? 'text-good' : 'text-bad'}`}>${t.pnl?.toFixed(2) || '0.00'}</span>
                  </div>
                ))}
                {(!dashboard?.recent_trades || dashboard.recent_trades.length === 0) && trades.length === 0 && <p className="text-ink-300 text-sm text-center py-8">No trades yet.</p>}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'signals' && (
          <div className="space-y-2">
            {signals.length === 0 ? <p className="text-ink-300 text-sm text-center py-12">No signals generated. Click Scan Now.</p> : signals.map((s: any) => (
              <div key={s.id} className="card p-5 animate-slide-up">
                <div className="flex items-start justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-4">
                    <span className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${s.direction === 'long' ? 'bg-good-bg text-good' : 'bg-bad-bg text-bad'}`}>{s.direction === 'long' ? 'LONG' : 'SHORT'}</span>
                    <div>
                      <h4 className="font-semibold text-ink-900">{s.symbol}</h4>
                      <div className="flex gap-4 text-xs text-ink-300 mt-1">
                        <span>Entry: ${s.entry_price}</span><span>SL: ${s.stop_loss}</span><span>TP: ${s.take_profit}</span>
                      </div>
                      <p className="text-xs text-ink-300 mt-2">{s.reason}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className={`text-lg font-bold ${s.confidence_score >= 70 ? 'text-good' : 'text-amber-600'}`}>{s.confidence_score}%</p>
                      <p className="text-xs text-ink-300">1:{s.risk_reward_ratio?.toFixed(1)} R:R</p>
                    </div>
                    {s.status === 'pending' && (
                      <div className="flex gap-2">
                        <button onClick={() => handleApprove(s.id, 'approve')} className="px-3 py-1.5 bg-good-bg text-good rounded-lg text-xs font-medium hover:opacity-80"><Play size={12} className="inline" /> Trade</button>
                        <button onClick={() => handleApprove(s.id, 'reject')} className="px-3 py-1.5 bg-bad-bg text-bad rounded-lg text-xs font-medium hover:opacity-80"><XCircle size={12} className="inline" /> Reject</button>
                      </div>
                    )}
                    <span className={`text-xs px-2 py-1 rounded-full capitalize ${s.status === 'pending' ? 'bg-amber-100 text-amber-700' : s.status === 'approved' ? 'bg-accent/10 text-accent' : s.status === 'rejected' ? 'bg-bad-bg text-bad' : 'bg-good-bg text-good'}`}>{s.status}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'trades' && (
          <div>
            <div className="space-y-2">
              {trades.length === 0 ? <p className="text-ink-300 text-sm text-center py-12">No trades yet.</p> : trades.map((t: any) => (
                <div key={t.id} className="card p-5 animate-slide-up cursor-pointer hover:border-accent/30 transition-all" onClick={() => { setChartSymbol(t.symbol); setChartTrade(t) }}>
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <div className="flex items-center gap-4">
                      <span className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${t.direction === 'long' ? 'bg-good-bg text-good' : 'bg-bad-bg text-bad'}`}>{t.direction === 'long' ? 'LONG' : 'SHORT'}</span>
                      <div>
                        <h4 className="font-semibold text-ink-900">{t.symbol}</h4>
                        <div className="flex gap-4 text-xs text-ink-300 mt-1">
                          <span>Entry: ${t.entry_price}</span>{t.exit_price && <span>Exit: ${t.exit_price}</span>}<span>Qty: {t.quantity}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <button onClick={(e) => { e.stopPropagation(); setChartSymbol(t.symbol); setChartTrade(t) }} className="p-2 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors" title="View Chart"><CandlestickChart size={16} /></button>
                      <div className="text-right">
                        <p className={`text-lg font-bold ${(t.pnl || 0) >= 0 ? 'text-good' : 'text-bad'}`}>${t.pnl?.toFixed(2) || '0.00'}</p>
                        {t.pnl_percentage != null && <p className={`text-xs ${(t.pnl_percentage || 0) >= 0 ? 'text-good' : 'text-bad'}`}>{t.pnl_percentage?.toFixed(1)}%</p>}
                      </div>
                      {t.status === 'open' && <button onClick={(e) => { e.stopPropagation(); handleCloseTrade(t.id) }} className="px-3 py-1.5 bg-bad-bg text-bad rounded-lg text-xs font-medium hover:opacity-80"><XCircle size={12} className="inline" /> Close</button>}
                      <span className={`text-xs px-2 py-1 rounded-full capitalize ${t.status === 'open' ? 'bg-good-bg text-good' : 'bg-black/5 text-ink-300'}`}>{t.status}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-ink-300 text-center mt-4">Click any trade to view chart 📊</p>
          </div>
        )}

        {activeTab === 'analysis' && (
          <div>
            <div className="card p-6 mb-6">
              <h3 className="font-semibold mb-4 flex items-center gap-2 text-ink-900"><Eye size={16} className="text-accent" /> On-demand AI Analysis</h3>
              <div className="flex gap-3">
                <input value={analysisSymbol} onChange={e => setAnalysisSymbol(e.target.value)} placeholder="Enter symbol (e.g. BTC/USDT, TSLA, AAPL)" className="flex-1 px-4 py-2.5 glass-input rounded-xl text-sm text-ink-900 outline-none focus:border-accent/50" onKeyDown={e => e.key === 'Enter' && handleAnalyze()} />
                <button onClick={handleAnalyze} disabled={analyzing} className="px-6 py-2.5 bg-accent hover:bg-accent-600 text-white rounded-xl text-sm font-medium flex items-center gap-2">
                  {analyzing ? <Loader2 className="animate-spin" size={14} /> : <Zap size={14} />} Analyze
                </button>
              </div>
            </div>
            {analysisResult && (
              <div className="card p-6 animate-slide-up">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="font-semibold text-lg text-ink-900">{analysisResult.symbol} — AI Analysis</h3>
                  <span className={`px-3 py-1 rounded-full text-sm font-bold ${analysisResult.direction === 'long' ? 'bg-good-bg text-good' : analysisResult.direction === 'short' ? 'bg-bad-bg text-bad' : 'bg-black/5 text-ink-300'}`}>{analysisResult.direction.toUpperCase()}</span>
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                  {[
                    { label: 'Entry Price', value: `$${analysisResult.entry_price}` },
                    { label: 'Stop Loss', value: `$${analysisResult.stop_loss}` },
                    { label: 'Take Profit', value: `$${analysisResult.take_profit}` },
                    { label: 'Confidence', value: `${analysisResult.confidence_score}%`, good: analysisResult.confidence_score >= 70 },
                    { label: 'Risk/Reward', value: `1:${analysisResult.risk_reward_ratio?.toFixed(1)}` },
                    { label: 'Risk %', value: `${analysisResult.risk_percentage}%` },
                    { label: 'News Sentiment', value: analysisResult.news_sentiment },
                    { label: 'Direction', value: analysisResult.direction.toUpperCase() },
                  ].map((item, i) => (
                    <div key={i} className="bg-black/5 rounded-xl p-3">
                      <p className="text-xs text-ink-300 mb-1">{item.label}</p>
                      <p className={`font-semibold ${item.good ? 'text-good' : 'text-ink-900'}`}>{item.value}</p>
                    </div>
                  ))}
                </div>
                <div className="space-y-4">
                  <div><p className="text-xs text-ink-500 mb-1 font-medium">Reason</p><p className="text-sm text-ink-700">{analysisResult.reason}</p></div>
                  <div><p className="text-xs text-ink-500 mb-1 font-medium">Trade Explanation</p><p className="text-sm text-ink-700">{analysisResult.trade_explanation}</p></div>
                  <div><p className="text-xs text-ink-500 mb-1 font-medium">Market Context</p><p className="text-sm text-ink-700">{analysisResult.market_context}</p></div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chart Modal */}
      {chartSymbol && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setChartSymbol(null)}>
          <div className="w-full max-w-4xl bg-[#0d0d1a] rounded-2xl p-5 border border-white/10" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="font-bold text-lg text-white">{chartSymbol}</h3>
                {chartTrade && (
                  <p className="text-sm text-gray-400">
                    {chartTrade.direction === 'long' ? '🟢' : '🔴'} {chartTrade.direction.toUpperCase()} · Entry: ${chartTrade.entry_price}
                    {chartTrade.exit_price && ` → Exit: $${chartTrade.exit_price}`} · PnL: ${chartTrade.pnl?.toFixed(2) || '0.00'}
                  </p>
                )}
              </div>
              <button onClick={() => setChartSymbol(null)} className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/20 transition-all">✕</button>
            </div>
            <TradeChart symbol={chartSymbol} entryPrice={chartTrade?.entry_price} exitPrice={chartTrade?.exit_price} tradeType={chartTrade?.direction} />
          </div>
        </div>
      )}
    </div>
  )
}
