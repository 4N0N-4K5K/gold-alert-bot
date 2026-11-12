import urllib.request
import json
import pandas as pd
import numpy as np
import datetime
import time
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import winsound
except ImportError:
    winsound = None

DATA_DIR = r"C:\Users\athul\.gemini\antigravity\scratch\xauusd_prop_firm_strategy"

# ----------------- TELEGRAM CONFIGURATION -----------------
TELEGRAM_BOT_TOKEN = "8425315044:AAHagTkkrdZxTWXB3tjT2ysfxOKftHz7vcs"
TELEGRAM_CHAT_ID   = "1507396633"

# ----------------- LIGHTWEIGHT CLOUD HEALTH CHECK SERVER -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Apex Institutional XAUUSD Live Alert Bot is Running 24/7.")
    def log_message(self, format, *args):
        pass # Suppress HTTP access logs

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Health server info: {e}")

# Start health check server in background daemon thread for Render Web Service compatibility
threading.Thread(target=start_health_server, daemon=True).start()

def send_telegram_alert(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            encoded_msg = urllib.parse.quote(message)
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={encoded_msg}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"[Telegram Error] Could not send notification: {e}")

def play_alert_sound():
    if winsound:
        try:
            winsound.Beep(880, 200)
            winsound.Beep(1175, 200)
            winsound.Beep(1568, 300)
        except Exception:
            pass

def fetch_tradingview_fxcm_quote():
    url = "https://scanner.tradingview.com/cfd/scan"
    payload = {
        "symbols": {"tickers": ["FX:XAUUSD"]},
        "columns": [
            "close", "open|5", "high|5", "low|5", "close|5",
            "open[1]|5", "high[1]|5", "low[1]|5", "close[1]|5",
            "EMA200|5", "ATR|5"
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        with urllib.request.urlopen(req, timeout=6) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data and 'data' in res_data and len(res_data['data']) > 0:
                d = res_data['data'][0]['d']
                return {
                    'live_price': float(d[0]),
                    'curr_open': float(d[1]), 'curr_high': float(d[2]), 'curr_low': float(d[3]), 'curr_close': float(d[4]),
                    'prev_open': float(d[5]), 'prev_high': float(d[6]), 'prev_low': float(d[7]), 'prev_close': float(d[8]),
                    'ema200': float(d[9]), 'atr': float(d[10]) if d[10] is not None else 4.5
                }
    except Exception:
        pass
    return None

def fetch_historical_5m_sequence():
    url = "https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=5m&limit=50"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = json.loads(response.read().decode('utf-8'))
            highs = [float(k[2]) for k in raw]
            lows  = [float(k[3]) for k in raw]
            return highs, lows
    except Exception:
        return None, None

def run_live_monitor():
    print("=" * 70)
    print("🚀 APEX INSTITUTIONAL XAUUSD LIVE SPOT ALERT ENGINE")
    print("   Data Feed: FXCM:XAUUSD (Direct TradingView Real-Time Feed)")
    print("   Timeframe: 5-Minute (M5)")
    print("   Strategy: Apex V6.4 Micro-Sweep (200 EMA Trend + Micro-Liquidity Grab)")
    print("   Cloud Server: Online (Health check active on port 10000)")
    print("=" * 70)
    
    last_candle_close = None
    
    while True:
        try:
            tv_data = fetch_tradingview_fxcm_quote()
            if tv_data is not None:
                live_price = tv_data['live_price']
                prev_close = tv_data['prev_close']
                prev_high  = tv_data['prev_high']
                prev_low   = tv_data['prev_low']
                prev_open  = tv_data['prev_open']
                ema200     = tv_data['ema200']
                atr_val    = tv_data['atr']
                
                if prev_close != last_candle_close:
                    last_candle_close = prev_close
                    current_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    hist_h, hist_l = fetch_historical_5m_sequence()
                    if hist_h and len(hist_h) >= 12:
                        sh = max(hist_h[-10:-2])
                        sl_struct = min(hist_l[-10:-2])
                    else:
                        sh = prev_high + 2.0
                        sl_struct = prev_low - 2.0
                        
                    bull_trend = prev_close > ema200
                    bear_trend = prev_close < ema200
                    
                    c_range = max(prev_high - prev_low, 0.01)
                    body_ratio = abs(prev_close - prev_open) / c_range
                    
                    is_bull_setup = bull_trend and (prev_close > prev_open) and (body_ratio >= 0.40) and (live_price > prev_high)
                    is_bear_setup = bear_trend and (prev_close < prev_open) and (body_ratio >= 0.40) and (live_price < prev_low)
                    
                    if is_bull_setup:
                        sl_price = round(prev_low - 0.30 * atr_val, 2)
                        sl_dist = round(live_price - sl_price, 2)
                        tp_price = round(live_price + 1.8 * sl_dist, 2)
                        lots = round((125.0 / sl_dist) * 0.01, 2)
                        
                        alert_msg = (
                            f"\n{'='*65}\n"
                            f"🟢 [APEX SPOT GOLD BUY SIGNAL TRIGGERED]\n"
                            f"Time:        {current_time_str}\n"
                            f"Instrument:  FXCM:XAUUSD (Spot Gold)\n"
                            f"Entry Price: ${live_price:.2f}\n"
                            f"Stop Loss:   ${sl_price:.2f} (Risk Distance: ${sl_dist:.2f})\n"
                            f"Take Profit: ${tp_price:.2f} (Target 1:1.8 RR: +${1.8*sl_dist:.2f})\n"
                            f"Prop Risk:   $125.00 (0.50% on $25,000 account)\n"
                            f"Recommended MT5 Lot Size: {lots} Lots\n"
                            f"{'='*65}\n"
                        )
                        print(alert_msg)
                        play_alert_sound()
                        send_telegram_alert(alert_msg)
                    elif is_bear_setup:
                        sl_price = round(prev_high + 0.30 * atr_val, 2)
                        sl_dist = round(sl_price - live_price, 2)
                        tp_price = round(live_price - 1.8 * sl_dist, 2)
                        lots = round((125.0 / sl_dist) * 0.01, 2)
                        
                        alert_msg = (
                            f"\n{'='*65}\n"
                            f"🔴 [APEX SPOT GOLD SELL SIGNAL TRIGGERED]\n"
                            f"Time:        {current_time_str}\n"
                            f"Instrument:  FXCM:XAUUSD (Spot Gold)\n"
                            f"Entry Price: ${live_price:.2f}\n"
                            f"Stop Loss:   ${sl_price:.2f} (Risk Distance: ${sl_dist:.2f})\n"
                            f"Take Profit: ${tp_price:.2f} (Target 1:1.8 RR: +${1.8*sl_dist:.2f})\n"
                            f"Prop Risk:   $125.00 (0.50% on $25,000 account)\n"
                            f"Recommended MT5 Lot Size: {lots} Lots\n"
                            f"{'='*65}\n"
                        )
                        print(alert_msg)
                        play_alert_sound()
                        send_telegram_alert(alert_msg)
                    else:
                        trend_text = "BULLISH (Up)" if prev_close > ema200 else "BEARISH (Down)"
                        print(f"[{current_time_str}] FXCM Live Tick: ${live_price:.2f} | Last 5m Close: ${prev_close:.2f} | 200 EMA: ${ema200:.2f} | Trend: {trend_text}")
                        
            time.sleep(20)
        except Exception as e:
            print(f"Monitor status: {e}")
            time.sleep(20)

if __name__ == "__main__":
    run_live_monitor()
