# app.py
from flask import Flask, send_file
import matplotlib
matplotlib.use("Agg")  # Required for Render (no GUI)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import io

app = Flask(__name__)


# -----------------------------
# DATA + INDICATORS
# -----------------------------
def get_btc_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    btc = yf.download(
        "BTC-USD",
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False
    )

    if btc.empty:
        raise ValueError("No BTC data received from Yahoo Finance")

    if isinstance(btc.columns, pd.MultiIndex):
        btc.columns = [c[0] if isinstance(c, tuple) else c for c in btc.columns]

    # EMA
    btc["EMA_12"] = btc["Close"].ewm(span=12, adjust=False).mean()
    btc["EMA_26"] = btc["Close"].ewm(span=26, adjust=False).mean()
    btc["EMA_50"] = btc["Close"].ewm(span=50, adjust=False).mean()

    # MACD
    ema_fast = btc["Close"].ewm(span=12, adjust=False).mean()
    ema_slow = btc["Close"].ewm(span=26, adjust=False).mean()
    btc["MACD"] = ema_fast - ema_slow
    btc["MACD_Signal"] = btc["MACD"].ewm(span=9, adjust=False).mean()
    btc["MACD_Hist"] = btc["MACD"] - btc["MACD_Signal"]

    # RSI
    delta = btc["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    btc["RSI"] = 100 - (100 / (1 + rs))

    return btc


# -----------------------------
# CHART GENERATION
# -----------------------------
def create_analysis_chart():
    btc = get_btc_data()

    fig = plt.figure(figsize=(15, 12))
    fig.suptitle("Bitcoin (BTC-USD) Teknik Analiz", fontsize=16, fontweight="bold")

    # ---- PRICE + EMA ----
    ax1 = plt.subplot(4, 1, 1)
    ax1.plot(btc.index, btc["Close"], label="Close", color="black", linewidth=2)
    ax1.plot(btc.index, btc["EMA_12"], label="EMA 12", color="blue", alpha=0.7)
    ax1.plot(btc.index, btc["EMA_26"], label="EMA 26", color="red", alpha=0.7)
    ax1.plot(btc.index, btc["EMA_50"], label="EMA 50", color="green", alpha=0.7)
    ax1.set_title("Price & Moving Averages")
    ax1.legend()
    ax1.grid(alpha=0.3)

    # ---- MACD ----
    ax2 = plt.subplot(4, 1, 2)
    ax2.plot(btc.index, btc["MACD"], label="MACD", color="blue")
    ax2.plot(btc.index, btc["MACD_Signal"], label="Signal", color="red")
    ax2.bar(btc.index, btc["MACD_Hist"], label="Histogram", color="gray", alpha=0.4)
    ax2.axhline(0, color="black", linestyle="--", linewidth=0.7)
    ax2.set_title("MACD")
    ax2.legend()
    ax2.grid(alpha=0.3)

    # ---- RSI ----
    ax3 = plt.subplot(4, 1, 3)
    ax3.plot(btc.index, btc["RSI"], label="RSI", color="purple", linewidth=2)
    ax3.axhline(70, color="red", linestyle="--", linewidth=1)
    ax3.axhline(30, color="green", linestyle="--", linewidth=1)
    ax3.set_ylim(0, 100)
    ax3.fill_between(btc.index, 30, 70, color="gray", alpha=0.1)
    ax3.set_title("RSI")
    ax3.grid(alpha=0.3)

    # ---- VOLUME ----
    ax4 = plt.subplot(4, 1, 4)
    ax4.bar(btc.index, btc["Volume"], color="steelblue", alpha=0.6)
    ax4.set_title("Volume")
    ax4.grid(alpha=0.3)

    # Format dates
    for ax in [ax1, ax2, ax3, ax4]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    # Save to bytes for web usage
    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    img_bytes.seek(0)
    return img_bytes


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    btc = get_btc_data()
    last_close = float(btc["Close"].iloc[-1])
    price = f"${last_close:,.2f}"

    html = f"""
    <html>
    <head>
        <title>BTC Technical Dashboard</title>
        <style>
            body {{
                font-family: Arial;
                text-align: center;
                margin: 40px;
            }}
        </style>
    </head>
    <body>
        <h1>Bitcoin Technical Dashboard</h1>
        <h2>Latest Price: {price}</h2>
        <img src="/chart" width="900"/>
    </body>
    </html>
    """
    return html


@app.route("/chart")
def chart():
    try:
        img = create_analysis_chart()
        return send_file(img, mimetype="image/png")
    except Exception as e:
        return f"Error: {str(e)}", 500


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
