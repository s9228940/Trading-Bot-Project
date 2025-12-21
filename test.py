from flask import Flask, send_file, request, jsonify
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import io
import anthropic
import os

app = Flask(__name__)

# Get API key from environment variable
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

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
    ax1.plot(df.index, df["EMA_12"], label="EMA 12", alpha=0.7)
    ax1.plot(df.index, df["EMA_26"], label="EMA 26", alpha=0.7)
    ax1.plot(df.index, df["EMA_50"], label="EMA 50", alpha=0.7)
    ax1.set_ylabel("Price (USD)")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2 = plt.subplot(4, 1, 2)
    ax2.plot(df.index, df["MACD"], label="MACD")
    ax2.plot(df.index, df["MACD_Signal"], label="Signal")
    ax2.bar(df.index, df["MACD_Hist"], alpha=0.4, label="Histogram")
    ax2.axhline(0, color="black", linestyle="--")
    ax2.set_ylabel("MACD")
    ax2.legend()
    ax2.grid(alpha=0.3)

    ax3 = plt.subplot(4, 1, 3)
    ax3.plot(df.index, df["RSI"], color="purple", label="RSI")
    ax3.axhline(70, color="red", linestyle="--", alpha=0.5, label="Overbought")
    ax3.axhline(30, color="green", linestyle="--", alpha=0.5, label="Oversold")
    ax3.set_ylim(0, 100)
    ax3.set_ylabel("RSI")
    ax3.legend()
    ax3.grid(alpha=0.3)

    ax4 = plt.subplot(4, 1, 4)
    ax4.bar(df.index, df["Volume"], alpha=0.6, color="blue")
    ax4.set_ylabel("Volume")
    ax4.grid(alpha=0.3)

    for ax in [ax1, ax2, ax3, ax4]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf, df


# -----------------------------
# AI ANALYSIS
# -----------------------------
def get_ai_analysis(symbol, df):
    """Get AI analysis of the technical indicators"""
    if not ANTHROPIC_API_KEY:
        return "AI analysis unavailable: API key not configured. Please set ANTHROPIC_API_KEY environment variable."
    
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Calculate trends
        price_change = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100
        
        prompt = f"""Analyze this cryptocurrency technical data for {COINS[symbol]} ({symbol}):

Current Price: ${latest['Close']:.2f}
24h Change: {price_change:.2f}%

Technical Indicators:
- EMA 12: ${latest['EMA_12']:.2f}
- EMA 26: ${latest['EMA_26']:.2f}
- EMA 50: ${latest['EMA_50']:.2f}
- MACD: {latest['MACD']:.4f}
- MACD Signal: {latest['MACD_Signal']:.4f}
- MACD Histogram: {latest['MACD_Hist']:.4f}
- RSI: {latest['RSI']:.2f}

Provide a brief technical analysis (3-4 sentences) covering:
1. Overall trend (bullish/bearish/neutral)
2. What the indicators suggest
3. Key support/resistance levels if relevant
Keep it concise and actionable."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return message.content[0].text
    except Exception as e:
        return f"Analysis unavailable: {str(e)}"


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
    
    # Get AI analysis
    analysis = get_ai_analysis(symbol, df)

    options = "".join(
        f'<option value="{k}" {"selected" if k==symbol else ""}>{v}</option>'
        for k, v in COINS.items()
    )

    return f"""
    <html>
    <head>
        <title>Crypto Dashboard</title>
        <style>
            body {{
                text-align: center;
                font-family: Arial, sans-serif;
                background: #f5f5f5;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
            }}
            h2 {{
                color: #4CAF50;
                margin-top: 5px;
            }}
            select {{
                padding: 10px 20px;
                font-size: 16px;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                background: white;
                cursor: pointer;
                margin: 20px 0;
            }}
            select:hover {{
                background: #f0f0f0;
            }}
            .analysis-box {{
                background: #e8f5e9;
                border-left: 4px solid #4CAF50;
                padding: 20px;
                margin: 20px 0;
                text-align: left;
                border-radius: 5px;
            }}
            .analysis-box h3 {{
                margin-top: 0;
                color: #2E7D32;
            }}
            .analysis-box p {{
                color: #333;
                line-height: 1.6;
            }}
            img {{
                max-width: 100%;
                height: auto;
                margin-top: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{COINS[symbol]} Dashboard</h1>
            <h2>Current Price: ${price:,.2f}</h2>

            <form method="get">
                <select name="coin" onchange="this.form.submit()">
                    {options}
                </select>
            </form>

            <div class="analysis-box">
                <h3>🤖 AI Technical Analysis</h3>
                <p>{analysis}</p>
            </div>

            <img src="/chart?coin={symbol}" width="100%"/>
        </div>
    </body>
    </html>
    """


@app.route("/chart")
def chart():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        return "Invalid coin", 400

    img, _ = create_chart(symbol)
    return send_file(img, mimetype="image/png")


@app.route("/api/analysis")
def api_analysis():
    """API endpoint for getting just the analysis"""
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        return jsonify({"error": "Invalid coin"}), 400
    
    df = get_crypto_data(symbol)
    analysis = get_ai_analysis(symbol, df)
    
    return jsonify({
        "symbol": symbol,
        "name": COINS[symbol],
        "analysis": analysis
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
