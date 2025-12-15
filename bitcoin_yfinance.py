from flask import Flask, send_file, request
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import io

app = Flask(__name__)

# -----------------------------
# SUPPORTED COINS
# -----------------------------
COINS = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "USDT": "Tether",
    "USDC": "USD Coin",
    "BNB": "BNB",
    "SOL": "Solana",
    "XRP": "XRP",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "LTC": "Litecoin",
    "DOT": "Polkadot",
    "XMR": "Monero",
    "LINK": "Chainlink",
    "MATIC": "Polygon",
}

# -----------------------------
# DATA + INDICATORS
# -----------------------------
def get_crypto_data(symbol):
    end = datetime.now()
    start = end - timedelta(days=90)

    ticker = f"{symbol}-USD"
    df = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False
    )

    if df.empty:
        raise ValueError("No data returned")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    # EMA
    df["EMA_12"] = df["Close"].ewm(span=12).mean()
    df["EMA_26"] = df["Close"].ewm(span=26).mean()
    df["EMA_50"] = df["Close"].ewm(span=50).mean()

    # MACD
    ema_fast = df["Close"].ewm(span=12).mean()
    ema_slow = df["Close"].ewm(span=26).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_Signal"] = df["MACD"].ewm(span=9).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # RSI
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df


# -----------------------------
# CHART
# -----------------------------
def create_chart(symbol):
    df = get_crypto_data(symbol)
    name = COINS[symbol]

    fig = plt.figure(figsize=(15, 12))
    fig.suptitle(f"{name} ({symbol}-USD) Technical Analysis", fontsize=16)

    ax1 = plt.subplot(4, 1, 1)
    ax1.plot(df.index, df["Close"], label="Close", color="black")
    ax1.plot(df.index, df["EMA_12"], label="EMA 12")
    ax1.plot(df.index, df["EMA_26"], label="EMA 26")
    ax1.plot(df.index, df["EMA_50"], label="EMA 50")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2 = plt.subplot(4, 1, 2)
    ax2.plot(df.index, df["MACD"], label="MACD")
    ax2.plot(df.index, df["MACD_Signal"], label="Signal")
    ax2.bar(df.index, df["MACD_Hist"], alpha=0.4)
    ax2.axhline(0, color="black", linestyle="--")
    ax2.legend()
    ax2.grid(alpha=0.3)

    ax3 = plt.subplot(4, 1, 3)
    ax3.plot(df.index, df["RSI"], color="purple")
    ax3.axhline(70, color="red", linestyle="--")
    ax3.axhline(30, color="green", linestyle="--")
    ax3.set_ylim(0, 100)
    ax3.grid(alpha=0.3)

    ax4 = plt.subplot(4, 1, 4)
    ax4.bar(df.index, df["Volume"], alpha=0.6)
    ax4.grid(alpha=0.3)

    for ax in [ax1, ax2, ax3, ax4]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        symbol = "BTC"

    df = get_crypto_data(symbol)
    price = float(df["Close"].iloc[-1])

    options = "".join(
        f'<option value="{k}" {"selected" if k==symbol else ""}>{v}</option>'
        for k, v in COINS.items()
    )

    return f"""
    <html>
    <head>
        <title>Crypto Dashboard</title>
    </head>
    <body style="text-align:center;font-family:Arial;">
        <h1>{COINS[symbol]} Dashboard</h1>
        <h2>Price: ${price:,.2f}</h2>

        <form method="get">
            <select name="coin" onchange="this.form.submit()">
                {options}
            </select>
        </form>

        <img src="/chart?coin={symbol}" width="900"/>
    </body>
    </html>
    """


@app.route("/chart")
def chart():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        return "Invalid coin", 400

    img = create_chart(symbol)
    return send_file(img, mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
