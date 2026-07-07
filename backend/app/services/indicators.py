import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from loguru import logger

class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def calculate_ema(df: pd.DataFrame, period: int) -> pd.Series:
        return df['close'].ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_macd(df: pd.DataFrame) -> Dict[str, pd.Series]:
        ema_12 = TechnicalIndicators.calculate_ema(df, 12)
        ema_26 = TechnicalIndicators.calculate_ema(df, 26)
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        return {
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram
        }

    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Dict[str, pd.Series]:
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        return {
            'upper': sma + (std * std_dev),
            'middle': sma,
            'lower': sma - (std * std_dev)
        }

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.Series:
        vwap = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        return vwap

    @staticmethod
    def calculate_momentum(df: pd.DataFrame, period: int = 10) -> pd.Series:
        return df['close'].diff(period)

    @staticmethod
    def calculate_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
        avg_volume = df['volume'].rolling(window=period).mean()
        return df['volume'] / avg_volume

    @staticmethod
    def find_support_resistance(df: pd.DataFrame, window: int = 5) -> Tuple[float, float]:
        levels = []
        for i in range(window, len(df) - window):
            if all(df['high'].iloc[i] >= df['high'].iloc[i - j] for j in range(1, window + 1)) and \
               all(df['high'].iloc[i] >= df['high'].iloc[i + j] for j in range(1, window + 1)):
                levels.append(('resistance', df['high'].iloc[i], df.index[i]))
            if all(df['low'].iloc[i] <= df['low'].iloc[i - j] for j in range(1, window + 1)) and \
               all(df['low'].iloc[i] <= df['low'].iloc[i + j] for j in range(1, window + 1)):
                levels.append(('support', df['low'].iloc[i], df.index[i]))

        resistances = [l[1] for l in levels if l[0] == 'resistance']
        supports = [l[1] for l in levels if l[0] == 'support']
        r1 = sorted(resistances, reverse=True)[:3] if resistances else [df['high'].max()]
        s1 = sorted(supports)[:3] if supports else [df['low'].min()]
        return (s1[0] if s1 else df['low'].min(), r1[0] if r1 else df['high'].max())

    @staticmethod
    def detect_candlestick_patterns(df: pd.DataFrame) -> Dict[str, bool]:
        patterns = {}
        if len(df) < 2:
            return {}
        last = df.iloc[-1]
        prev = df.iloc[-2]
        body = abs(last['close'] - last['open'])
        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        total_range = last['high'] - last['low']

        patterns['doji'] = body < (total_range * 0.1)
        patterns['hammer'] = lower_wick > (body * 2) and upper_wick < (body * 0.5) and body > 0
        patterns['shooting_star'] = upper_wick > (body * 2) and lower_wick < (body * 0.3) and body > 0
        patterns['engulfing_bullish'] = prev['close'] < prev['open'] and last['close'] > last['open'] and last['open'] < prev['close'] and last['close'] > prev['open']
        patterns['engulfing_bearish'] = prev['close'] > prev['open'] and last['close'] < last['open'] and last['open'] > prev['close'] and last['close'] < prev['open']
        patterns['three_white_soldiers'] = False
        patterns['three_black_crows'] = False
        if len(df) >= 3:
            c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
            patterns['three_white_soldiers'] = (
                c1['close'] > c1['open'] and
                c2['close'] > c2['open'] and
                c3['close'] > c3['open'] and
                c2['close'] > c1['close'] and
                c3['close'] > c2['close']
            ) if len(df) >= 3 else False
        return patterns

    @staticmethod
    def detect_trend(df: pd.DataFrame) -> str:
        if len(df) < 50:
            return 'neutral'
        ema_20 = TechnicalIndicators.calculate_ema(df, 20)
        ema_50 = TechnicalIndicators.calculate_ema(df, 50)
        current_price = df['close'].iloc[-1]

        if current_price > ema_20.iloc[-1] > ema_50.iloc[-1]:
            return 'bullish'
        elif current_price < ema_20.iloc[-1] < ema_50.iloc[-1]:
            return 'bearish'
        else:
            return 'neutral'

    @staticmethod
    def detect_liquidity(df: pd.DataFrame) -> float:
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        recent_volume = df['volume'].iloc[-5:].mean()
        if avg_volume == 0:
            return 0
        return min(recent_volume / avg_volume, 2.0)

    @staticmethod
    def detect_breakout(df: pd.DataFrame, lookback: int = 20) -> Tuple[bool, str]:
        if len(df) < lookback:
            return False, 'none'
        recent_high = df['high'].iloc[-lookback:-1].max()
        recent_low = df['low'].iloc[-lookback:-1].min()
        current_close = df['close'].iloc[-1]
        if current_close > recent_high:
            return True, 'bullish_breakout'
        elif current_close < recent_low:
            return True, 'bearish_breakout'
        return False, 'none'

    @staticmethod
    def compute_all_indicators(df: pd.DataFrame) -> Dict:
        if df.empty or len(df) < 50:
            return {}
        try:
            rsi = TechnicalIndicators.calculate_rsi(df)
            macd = TechnicalIndicators.calculate_macd(df)
            bb = TechnicalIndicators.calculate_bollinger_bands(df)
            atr = TechnicalIndicators.calculate_atr(df)
            vwap = TechnicalIndicators.calculate_vwap(df)
            momentum = TechnicalIndicators.calculate_momentum(df)
            vol_ratio = TechnicalIndicators.calculate_volume_ratio(df)
            trend = TechnicalIndicators.detect_trend(df)
            patterns = TechnicalIndicators.detect_candlestick_patterns(df)
            support, resistance = TechnicalIndicators.find_support_resistance(df)
            breakout, breakout_type = TechnicalIndicators.detect_breakout(df)
            liquidity = TechnicalIndicators.detect_liquidity(df)

            last = df.iloc[-1]
            return {
                'rsi': round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else 50,
                'macd_line': round(macd['macd_line'].iloc[-1], 4) if not pd.isna(macd['macd_line'].iloc[-1]) else 0,
                'macd_signal': round(macd['signal_line'].iloc[-1], 4) if not pd.isna(macd['signal_line'].iloc[-1]) else 0,
                'macd_histogram': round(macd['histogram'].iloc[-1], 4) if not pd.isna(macd['histogram'].iloc[-1]) else 0,
                'bb_upper': round(bb['upper'].iloc[-1], 2) if not pd.isna(bb['upper'].iloc[-1]) else 0,
                'bb_middle': round(bb['middle'].iloc[-1], 2) if not pd.isna(bb['middle'].iloc[-1]) else 0,
                'bb_lower': round(bb['lower'].iloc[-1], 2) if not pd.isna(bb['lower'].iloc[-1]) else 0,
                'atr': round(atr.iloc[-1], 2) if not pd.isna(atr.iloc[-1]) else 0,
                'vwap': round(vwap.iloc[-1], 2) if not pd.isna(vwap.iloc[-1]) else 0,
                'ema_9': round(TechnicalIndicators.calculate_ema(df, 9).iloc[-1], 2),
                'ema_21': round(TechnicalIndicators.calculate_ema(df, 21).iloc[-1], 2),
                'ema_50': round(TechnicalIndicators.calculate_ema(df, 50).iloc[-1], 2),
                'ema_200': round(TechnicalIndicators.calculate_ema(df, 200).iloc[-1], 2) if len(df) >= 200 else 0,
                'momentum': round(momentum.iloc[-1], 2) if not pd.isna(momentum.iloc[-1]) else 0,
                'volume_ratio': round(vol_ratio.iloc[-1], 2) if not pd.isna(vol_ratio.iloc[-1]) else 1,
                'trend': trend,
                'support_1': round(support, 2),
                'resistance_1': round(resistance, 2),
                'liquidity_score': round(liquidity, 2),
                'breakout': breakout,
                'breakout_type': breakout_type,
                'patterns': patterns,
                'current_price': round(last['close'], 2),
                'current_volume': int(last['volume']),
            }
        except Exception as e:
            logger.error(f"Indicator computation error: {e}")
            return {}

indicators_service = TechnicalIndicators()
