const http = require('http');
const crypto = require('crypto');

const users = {};
const tokens = {};
let signals = [];
let trades = [];
let nextId = 1;

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization');
  if (req.method === 'OPTIONS') return res.end();

  let body = '';
  req.on('data', c => body += c);
  req.on('end', () => {
    const data = body ? JSON.parse(body) : {};
    const url = req.url.split('?')[0];
    const token = req.headers.authorization?.split(' ')[1];
    let user = tokens[token];

    const send = (code, d) => { res.writeHead(code, {'Content-Type':'application/json'}); res.end(JSON.stringify(d)); };

    // Auth
    if (url === '/api/auth/signup' && req.method === 'POST') {
      if (users[data.email]) return send(400, {message:'Email already registered'});
      const id = crypto.randomUUID();
      users[data.email] = { id, email: data.email, full_name: data.full_name || '', hashed_password: crypto.createHash('sha256').update(data.password).digest('hex'), trade_mode:'paper', max_risk_per_trade:2, max_daily_loss:5, max_drawdown:20, max_open_positions:5, min_confidence_score:65, min_risk_reward:2 };
      const t = crypto.randomUUID();
      tokens[t] = users[data.email];
      return send(200, { access_token: t, token_type:'bearer', user: { id, email: data.email, full_name: data.full_name || '', trade_mode:'paper', max_risk_per_trade:2, max_daily_loss:5, max_drawdown:20, max_open_positions:5, min_confidence_score:65, min_risk_reward:2 } });
    }
    if (url === '/api/auth/login' && req.method === 'POST') {
      const u = users[data.email];
      if (!u || u.hashed_password !== crypto.createHash('sha256').update(data.password).digest('hex')) return send(401, {message:'Invalid credentials'});
      const t = crypto.randomUUID();
      tokens[t] = u;
      return send(200, { access_token: t, token_type:'bearer', user: { id: u.id, email: u.email, full_name: u.full_name, trade_mode: u.trade_mode, max_risk_per_trade: u.max_risk_per_trade, max_daily_loss: u.max_daily_loss, max_drawdown: u.max_drawdown, max_open_positions: u.max_open_positions, min_confidence_score: u.min_confidence_score, min_risk_reward: u.min_risk_reward } });
    }
    if (!user) return send(401, {message:'Unauthorized'});

    // Dashboard
    if (url === '/api/dashboard' && req.method === 'GET') {
      const totalPnl = trades.reduce((s,t) => s + (t.pnl || 0), 0);
      const dailyPnl = trades.filter(t => t.status === 'closed').reduce((s,t) => s + (t.pnl || 0), 0);
      const closed = trades.filter(t => t.status === 'closed');
      const wins = closed.filter(t => t.pnl > 0).length;
      return send(200, {
        total_pnl: totalPnl, daily_pnl: dailyPnl, win_rate: closed.length ? Math.round(wins/closed.length*100*10)/10 : 0,
        open_positions: trades.filter(t => t.status === 'open').length, total_trades: trades.length,
        active_signals: signals.filter(s => s.status === 'pending').length, portfolio_value: 100000 + totalPnl,
        recent_trades: trades.slice(-5).reverse(), recent_signals: signals.slice(-5).reverse(), watchlist: []
      });
    }

    // Me
    if (url === '/api/me' && req.method === 'GET') {
      return send(200, { id: user.id, email: user.email, full_name: user.full_name, trade_mode: user.trade_mode, max_risk_per_trade: user.max_risk_per_trade, max_daily_loss: user.max_daily_loss, max_drawdown: user.max_drawdown, max_open_positions: user.max_open_positions, min_confidence_score: user.min_confidence_score, min_risk_reward: user.min_risk_reward, created_at: new Date().toISOString() });
    }

    // Scan
    if (url === '/api/scan' && req.method === 'POST') {
      const symbols = ['BTC/USD','ETH/USD','TSLA','AAPL','MSFT','GOOGL','AMZN','NVDA','META','SPY','QQQ'];
      const newSignals = [];
      for (const sym of symbols) {
        if (Math.random() > 0.4) continue;
        const dir = Math.random() > 0.5 ? 'long' : 'short';
        const price = sym.includes('USD') ? Math.random() * 50000 + 2000 : Math.random() * 500 + 50;
        const conf = Math.floor(Math.random() * 30) + 60;
        const rr = +(Math.random() * 2 + 1.5).toFixed(1);
        const sig = {
          id: crypto.randomUUID(), symbol: sym, direction: dir, entry_price: +price.toFixed(2),
          stop_loss: dir === 'long' ? +(price * (1 - Math.random()*0.05)).toFixed(2) : +(price * (1 + Math.random()*0.05)).toFixed(2),
          take_profit: dir === 'long' ? +(price * (1 + Math.random()*0.1)).toFixed(2) : +(price * (1 - Math.random()*0.1)).toFixed(2),
          confidence_score: conf, risk_reward_ratio: rr, risk_percentage: +(Math.random()*1.5+0.5).toFixed(1),
          reason: `${dir === 'long' ? 'Bullish' : 'Bearish'} breakout detected on ${sym} with strong volume confirmation. RSI showing ${dir === 'long' ? 'oversold bounce' : 'overbought rejection'}.`,
          trade_explanation: `The AI analysis indicates a ${dir} opportunity on ${sym} based on multi-timeframe confluence. Technical indicators show momentum favoring the ${dir} side.`,
          news_sentiment: ['bullish','bearish','neutral'][Math.floor(Math.random()*3)],
          market_context: `Market structure shows ${dir === 'long' ? 'higher highs and higher lows' : 'lower highs and lower lows'} on the 4H timeframe.`,
          status: 'pending', timeframe: '1h', created_at: new Date().toISOString()
        };
        signals.push(sig);
        newSignals.push(sig);
      }
      return send(200, { signals: signals.slice(-20).reverse(), scanned_symbols: symbols.length, scan_time: new Date().toISOString() });
    }

    // Signals
    if (url === '/api/signals' && req.method === 'GET') {
      const limit = parseInt(req.url.split('limit=')[1]) || 20;
      return send(200, signals.slice(-limit).reverse());
    }

    // Approve signal
    const sigMatch = url.match(/\/api\/signals\/([^/]+)\/approve/);
    if (sigMatch && req.method === 'POST') {
      const sig = signals.find(s => s.id === sigMatch[1]);
      if (!sig) return send(404, {message:'Signal not found'});
      if (data.action === 'reject') {
        sig.status = 'rejected';
        return send(200, {message:'Signal rejected', success:true});
      }
      sig.status = 'approved';
      const t = {
        id: crypto.randomUUID(), symbol: sig.symbol, direction: sig.direction,
        entry_price: sig.entry_price, exit_price: null, quantity: +(Math.random()*2+0.5).toFixed(2),
        stop_loss: sig.stop_loss, take_profit: sig.take_profit, status: 'open',
        pnl: null, pnl_percentage: null, risk_percentage: sig.risk_percentage,
        confidence_score: sig.confidence_score, trade_mode: 'paper',
        entry_time: new Date().toISOString(), exit_time: null, created_at: new Date().toISOString()
      };
      trades.push(t);
      return send(200, {message:'Trade executed in paper mode', success:true});
    }

    // Trades
    if (url === '/api/trades' && req.method === 'GET') {
      return send(200, trades.slice(-20).reverse());
    }

    // Close trade
    const trMatch = url.match(/\/api\/trades\/([^/]+)\/close/);
    if (trMatch && req.method === 'POST') {
      const t = trades.find(tr => tr.id === trMatch[1]);
      if (!t) return send(404, {message:'Trade not found'});
      t.exit_price = +(t.entry_price * (t.direction === 'long' ? 1 + Math.random()*0.06 : 1 - Math.random()*0.06)).toFixed(2);
      t.pnl = t.direction === 'long' ? +((t.exit_price - t.entry_price) * t.quantity).toFixed(2) : +((t.entry_price - t.exit_price) * t.quantity).toFixed(2);
      t.pnl_percentage = +((t.pnl / (t.entry_price * t.quantity)) * 100).toFixed(1);
      t.status = 'closed';
      t.exit_time = new Date().toISOString();
      return send(200, {message:`Trade closed. PnL: ${t.pnl}`, success:true});
    }

    // PnL
    if (url === '/api/pnl' && req.method === 'GET') {
      const closed = trades.filter(t => t.status === 'closed');
      const totalPnl = closed.reduce((s,t) => s + (t.pnl || 0), 0);
      const wins = closed.filter(t => t.pnl > 0).length;
      const losses = closed.filter(t => t.pnl < 0).length;
      return send(200, { daily_pnl: totalPnl * 0.3, total_pnl: totalPnl, win_rate: closed.length ? +Math.round(wins/closed.length*1000)/10 : 0, total_trades: closed.length, winning_trades: wins, losing_trades: losses });
    }

    // AI Analyze
    if (url === '/api/ai/analyze' && req.method === 'POST') {
      const price = data.symbol.includes('USD') ? Math.random()*50000+2000 : Math.random()*500+50;
      const dir = ['long','short','neutral'][Math.floor(Math.random()*3)];
      const conf = dir === 'neutral' ? Math.floor(Math.random()*20)+20 : Math.floor(Math.random()*25)+65;
      return send(200, {
        symbol: data.symbol, direction: dir, entry_price: +price.toFixed(2),
        stop_loss: dir === 'long' ? +(price*0.95).toFixed(2) : dir === 'short' ? +(price*1.05).toFixed(2) : +(price*0.97).toFixed(2),
        take_profit: dir === 'long' ? +(price*1.08).toFixed(2) : dir === 'short' ? +(price*0.92).toFixed(2) : +(price*1.03).toFixed(2),
        confidence_score: conf, risk_reward_ratio: 2.5, risk_percentage: 1.0,
        reason: `Multi-timeframe analysis for ${data.symbol} shows ${dir === 'neutral' ? 'mixed signals across indicators' : dir === 'long' ? 'bullish momentum with RSI trending up from oversold levels. Volume confirms accumulation.' : 'bearish divergence on RSI with MACD crossing down. Distribution pattern detected.'}`,
        trade_explanation: `Based on technical analysis across 1h, 4h, and 1d timeframes, the AI recommends a ${dir} position. Entry at support/resistance with tight stop loss.`,
        news_sentiment: ['bullish','bearish','neutral'][Math.floor(Math.random()*3)],
        market_context: `${data.symbol} is currently in a ${['uptrend','downtrend','range'][Math.floor(Math.random()*3)]} on higher timeframes.`,
        indicators_data: { rsi: Math.floor(Math.random()*40)+30, macd_line: +(Math.random()*2-1).toFixed(2), macd_signal: +(Math.random()*2-1).toFixed(2), trend: ['bullish','bearish','neutral'][Math.floor(Math.random()*3)], current_price: +price.toFixed(2) }
      });
    }

      // Broker switch
  if (url === '/api/broker/switch' && req.method === 'POST') {
    return send(200, {message:`Switched to ${data.broker}`, broker: data.broker, success:true});
  }
  // Get supported brokers
  if (url === '/api/broker/list' && req.method === 'GET') {
    return send(200, { brokers: [
      { id:'binance', label:'Binance', type:'crypto' }, { id:'bybit', label:'Bybit', type:'crypto' },
      { id:'okx', label:'OKX', type:'crypto' }, { id:'kucoin', label:'KuCoin', type:'crypto' },
      { id:'kraken', label:'Kraken', type:'crypto' }, { id:'coinbase', label:'Coinbase', type:'crypto' },
      { id:'gateio', label:'Gate.io', type:'crypto' }, { id:'bitget', label:'Bitget', type:'crypto' },
      { id:'mexc', label:'MEXC', type:'crypto' }, { id:'huobi', label:'Huobi', type:'crypto' },
      { id:'gemini', label:'Gemini', type:'crypto' }, { id:'bitfinex', label:'Bitfinex', type:'crypto' },
      { id:'coindcx', label:'CoinDCX', type:'crypto' },
      { id:'alpaca', label:'Alpaca', type:'stocks' }, { id:'dhan', label:'Dhan (India)', type:'stocks' },
      { id:'oanda', label:'OANDA', type:'forex' }, { id:'octafx', label:'OctaFX', type:'forex' },
    ]});
  }

  send(404, {message:'Not found'});
  });
});

const PORT = 8000;
server.listen(PORT, () => console.log(`Mock API running on http://localhost:${PORT}`));
