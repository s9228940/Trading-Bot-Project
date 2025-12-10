import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 1. FİNANSAL VERİYİ İNDİRME
print("Bitcoin verileri indiriliyor...")
end_date = datetime.now()
start_date = end_date - timedelta(days=90)  # Daha fazla veri = daha iyi indikatörler

# auto_adjust=True eklenerek sütun adlarının düzleştirilmesi sağlanır
btc = yf.download('BTC-USD', start=start_date, end=end_date, progress=False, auto_adjust=True)
print(f"✓ {len(btc)} günlük veri indirildi\n")

# Fix: Ensure column names are single-level strings
# This handles cases where yfinance might return MultiIndex columns
# even with auto_adjust=True, taking the first element of the tuple
# for columns like ('Close', 'BTC-USD') -> 'Close'
if isinstance(btc.columns, pd.MultiIndex):
    btc.columns = [col[0] if isinstance(col, tuple) else col for col in btc.columns]

# 2. TEKNİK İNDİKATÖRLERİN HESAPLANMASI

# EMA (Exponential Moving Average) - 12 ve 26 günlük
def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

btc['EMA_12'] = calculate_ema(btc['Close'], 12)
btc['EMA_26'] = calculate_ema(btc['Close'], 26)
btc['EMA_50'] = calculate_ema(btc['Close'], 50)

# MACD (Moving Average Convergence Divergence)
def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data.ewm(span=fast, adjust=False).mean()
    ema_slow = data.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

btc['MACD'], btc['MACD_Signal'], btc['MACD_Hist'] = calculate_macd(btc['Close'])

# RSI (Relative Strength Index)
def calculate_rsi(data, period=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

btc['RSI'] = calculate_rsi(btc['Close'])

print("Teknik İndikatörler Hesaplandı:")
print(f"✓ EMA (12, 26, 50 günlük)")
print(f"✓ MACD (12, 26, 9)")
print(f"✓ RSI (14 günlük)\n")

# 3. GÖRSELLEŞTİRME
fig = plt.figure(figsize=(15, 12))
fig.suptitle('Bitcoin (BTC-USD) Teknik Analiz', fontsize=16, fontweight='bold')

# Alt grafik 1: Fiyat ve EMA'lar
ax1 = plt.subplot(4, 1, 1)
ax1.plot(btc.index, btc['Close'], label='Kapanış Fiyatı', color='black', linewidth=2)
ax1.plot(btc.index, btc['EMA_12'], label='EMA 12', color='blue', linewidth=1.5, alpha=0.7)
ax1.plot(btc.index, btc['EMA_26'], label='EMA 26', color='red', linewidth=1.5, alpha=0.7)
ax1.plot(btc.index, btc['EMA_50'], label='EMA 50', color='green', linewidth=1.5, alpha=0.7)
ax1.set_ylabel('Fiyat (USD)', fontsize=10)
ax1.set_title('Bitcoin Fiyat ve Hareketli Ortalamalar (EMA)', fontsize=12)
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)

# Alt grafik 2: MACD
ax2 = plt.subplot(4, 1, 2)
ax2.plot(btc.index, btc['MACD'], label='MACD', color='blue', linewidth=1.5)
ax2.plot(btc.index, btc['MACD_Signal'], label='Signal', color='red', linewidth=1.5)
ax2.bar(btc.index, btc['MACD_Hist'], label='Histogram', color='gray', alpha=0.3)
ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
ax2.set_ylabel('MACD', fontsize=10)
ax2.set_title('MACD (Moving Average Convergence Divergence)', fontsize=12)
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3)

# Alt grafik 3: RSI
ax3 = plt.subplot(4, 1, 3)
ax3.plot(btc.index, btc['RSI'], label='RSI', color='purple', linewidth=2)
ax3.axhline(y=70, color='red', linestyle='--', linewidth=1, label='Aşırı Alım (70)')
ax3.axhline(y=30, color='green', linestyle='--', linewidth=1, label='Aşırı Satım (30)')
ax3.fill_between(btc.index, 30, 70, alpha=0.1, color='gray')
ax3.set_ylabel('RSI', fontsize=10)
ax3.set_title('RSI (Relative Strength Index)', fontsize=12)
ax3.set_ylim(0, 100)
ax3.legend(loc='upper left')
ax3.grid(True, alpha=0.3)

# Alt grafik 4: İşlem Hacmi
ax4 = plt.subplot(4, 1, 4)
ax4.bar(btc.index, btc['Volume'], color='steelblue', alpha=0.6)
ax4.set_ylabel('Hacim', fontsize=10)
ax4.set_xlabel('Tarih', fontsize=10)
ax4.set_title('İşlem Hacmi', fontsize=12)
ax4.grid(True, alpha=0.3)

# Tarih formatını düzenle
for ax in [ax1, ax2, ax3, ax4]:
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

plt.tight_layout()
plt.show()

# 4. İSTATİSTİKLER VE SİNYALLER
print("\n" + "="*60)
print("SON DURUM ANALİZİ")
print("="*60)

last_price = btc['Close'].iloc[-1]
last_rsi = btc['RSI'].iloc[-1]
last_macd = btc['MACD'].iloc[-1]
last_signal = btc['MACD_Signal'].iloc[-1]

print(f"Son Fiyat: ${last_price:,.2f}")
print(f"EMA 12: ${btc['EMA_12'].iloc[-1]:,.2f}")
print(f"EMA 26: ${btc['EMA_26'].iloc[-1]:,.2f}")
print(f"EMA 50: ${btc['EMA_50'].iloc[-1]:,.2f}")
print(f"\nRSI: {last_rsi:.2f}")

if last_rsi > 70:
    print("  → Aşırı Alım Bölgesi (Satış sinyali olabilir)")
elif last_rsi < 30:
    print("  → Aşırı Satım Bölgesi (Alış sinyali olabilir)")
else:
    print("  → Nötr Bölge")

print(f"\nMACD: {last_macd:.2f}")
print(f"MACD Signal: {last_signal:.2f}")

if last_macd > last_signal:
    print("  → Yükseliş Trendi (MACD > Signal)")
else:
    print("  → Düşüş Trendi (MACD < Signal)")

# Trend analizi
if btc['Close'].iloc[-1] > btc['EMA_12'].iloc[-1] > btc['EMA_26'].iloc[-1]:
    print("\n📈 GÜÇLÜ YÜKSELIŞ TRENDİ")
elif btc['Close'].iloc[-1] < btc['EMA_12'].iloc[-1] < btc['EMA_26'].iloc[-1]:
    print("\n📉 GÜÇLÜ DÜŞÜŞ TRENDİ")
else:
    print("\n➡️  YATAY/KARARSIZ TREND")

print("="*60)
print("\n⚠️  Not: Bu analiz sadece eğitim amaçlıdır.")
print("    Yatırım kararları için profesyonel danışman kullanın.")
