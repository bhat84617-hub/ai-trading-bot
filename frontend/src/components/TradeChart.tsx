'use client'
import { useEffect, useRef } from 'react'
import { createChart, ColorType, LineStyle } from 'lightweight-charts'
import { api } from '@/lib/api'

interface Props {
  symbol: string
  entryPrice?: number | null
  exitPrice?: number | null
  tradeType?: 'long' | 'short'
}

export default function TradeChart({ symbol, entryPrice, exitPrice, tradeType }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: '#0d0d1a' }, textColor: '#8888bb' },
      grid: { vertLines: { color: '#1a1a3a' }, horzLines: { color: '#1a1a3a' } },
      width: containerRef.current.clientWidth,
      height: 400,
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true, secondsVisible: false },
    })
    chartRef.current = chart
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00b894', downColor: '#e17055',
      borderUpColor: '#00b894', borderDownColor: '#e17055',
      wickUpColor: '#00b894', wickDownColor: '#e17055',
    })
    api.getCandles(symbol, '1h', 100).then(data => {
      if (data.candles?.length) {
        candleSeries.setData(data.candles.map((c: any) => ({
          time: Math.floor(c.timestamp / 1000),
          open: c.open, high: c.high, low: c.low, close: c.close,
        })))
      }
    }).catch(() => {})
    if (entryPrice) {
      const color = tradeType === 'long' ? '#00b894' : '#e17055'
      candleSeries.createPriceLine({ price: entryPrice, color, lineWidth: 2, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: `Entry $${entryPrice}` })
    }
    if (exitPrice) {
      candleSeries.createPriceLine({ price: exitPrice, color: '#fdcb6e', lineWidth: 2, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: `Exit $${exitPrice}` })
    }
    const handleResize = () => { if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth }) }
    window.addEventListener('resize', handleResize)
    return () => { window.removeEventListener('resize', handleResize); chart.remove() }
  }, [symbol, entryPrice, exitPrice, tradeType])

  return <div ref={containerRef} className="w-full rounded-xl overflow-hidden" />
}
