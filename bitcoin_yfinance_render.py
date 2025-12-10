import matplotlib
matplotlib.use('Agg')   # Use non-GUI backend for Render

import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 1. DOWNLOAD FINANCIAL DATA
print("Bitcoin verileri indiriliyor...")
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

btc = yf.download('BTC-USD', start=start_date, end=end_date, progress=False)

# Remove duplicated dates that break formatting
btc = btc[~btc.index.duplicated(keep='last')]

print(f"✓ {len(btc)} günlük veri indirildi\n")

# 2. TECHNICAL INDICATORS

# EMA
def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

btc['EMA_12'] = calculate_ema(btc['Close'], 12)
btc['EMA_26'] = calculate_ema(btc['Close'], 26)
btc['EMA_50'] = calculate_ema(btc['Close'], 50)

# MACD
def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data.ewm(span=fast, adjust=False).mean()
    ema_slow = data.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

btc['MACD'], btc['MACD_Signal'], btc['MACD_Hist'] = calculate_macd(btc['Close'])

# RSI
def calculate_rsi(data, period=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

btc['RSI'] = calculate_rsi(btc['Close'])

print("Teknik İndikatörler Hesaplandı:")
print("✓ EMA (12, 26, 50 günlük)")
print("✓ MACD (12, 26, 9)")
print("✓ RSI (14 günlük)\n")

# 3. CHART (Render-safe, saved instead of shown)

fig = plt.figure(figsize=(15, 12))
fig.suptitle('Bitcoin (BTC-USD) Teknik Analiz', fontsize=16, fontweight='bold')

# Price + EMAs
ax1 = plt.subplot(4, 1, 1)
ax1.plot(btc.index, btc['Close'], label='Close', color='black', linewidth=2)
ax1.plot(btc.index, btc['EMA_12'], label='EMA 12')
ax1.plot(btc.index, btc['EMA_26'], label='EMA 26')
ax1.plot(btc.index, btc['EMA_50'], label='EMA 50')
ax1.legend()
ax1.grid(True, alpha=0.3)

# MACD
ax2 = plt.subplot(4, 1, 2)
ax2.plot(btc.index, btc['MACD'], label='MACD')
ax2.plot(btc.index, btc['MACD_Signal'], label='Signal')
ax2.bar(btc.index, btc['MACD_Hist'], color='gray', alpha=0.3)
ax2.axhline(0, color='black', linewidth=0.8)
ax2.legend()
ax2.grid(True, alpha=0.3)

# RSI
ax3 = plt.subplot(4, 1, 3)
ax3.plot(btc.index, btc['RSI'], label='RSI', color='purple')
ax3.axhline(70, color='red', linestyle='--')
ax3.axhline(30, color='green', linestyle='--')
ax3.set_ylim(0, 100)
ax3.legend()
ax3.grid(True, alpha=0.3)


# replace NaN volumes



ax4 = plt.subplot(4, 1, 4)
volumes = btc['Volume'].fillna(0).values  # Convert to numpy array
ax4.bar(range(len(volumes)), volumes, color='steelblue', alpha=0.6)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("btc_analysis.png")
print("Grafik kaydedildi: btc_analysis.png")

# 4. ANALYSIS OUTPUT

# Convert all values to float to avoid Series formatting errors
last_price = float(btc['Close'].iloc[-1])
last_rsi = float(btc['RSI'].iloc[-1])
last_macd = float(btc['MACD'].iloc[-1])
last_signal = float(btc['MACD_Signal'].iloc[-1])

print("\n" + "="*60)
print("SON DURUM ANALİZİ")
print("="*60)

print(f"Son Fiyat: ${last_price:,.2f}")
print(f"EMA 12: ${float(btc['EMA_12'].iloc[-1]):,.2f}")
print(f"EMA 26: ${float(btc['EMA_26'].iloc[-1]):,.2f}")
print(f"EMA 50: ${float(btc['EMA_50'].iloc[-1]):,.2f}")

print(f"\nRSI: {last_rsi:.2f}")

if last_rsi > 70:
    print("  → Aşırı Alım (Satış sinyali)")
elif last_rsi < 30:
    print("  → Aşırı Satım (Alış sinyali)")
else:
    print("  → Nötr")

print(f"\nMACD: {last_macd:.4f}")
print(f"Signal: {last_signal:.4f}")

if last_macd > last_signal:
    print("  → Yükseliş Trendi")
else:
    print("  → Düşüş Trendi")

ema12 = float(btc['EMA_12'].iloc[-1])
ema26 = float(btc['EMA_26'].iloc[-1])

if last_price > ema12 > ema26:
    print("\n📈 GÜÇLÜ YÜKSELİŞ TRENDİ")
elif last_price < ema12 < ema26:
    print("\n📉 GÜÇLÜ DÜŞÜŞ TRENDİ")
else:
    print("\n➡️ YATAY / KARARSIZ TREND")

print("="*60)
print("Analiz tamamlandı. Grafik dosyaya kaydedildi.")
print("\n⚠️ Not: Bu analiz sadece eğitim amaçlıdır.")
print("    Yatırım kararları için profesyonel danışman kullanın.")
