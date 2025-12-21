from flask import Flask, send_file, request, jsonify, abort
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import io
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import anthropic

app = Flask(__name__)

# Config
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300
cache = Cache(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Expanded coin list (top cryptos as of late 2025)
COINS = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "XRP": "XRP",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "AVAX": "Avalanche",
    "TRX": "TRON",
    "LINK": "Chainlink",
    "DOT": "Polkadot",
    "MATIC": "Polygon",
    "LTC": "Litecoin",
    "SHIB": "Shiba Inu",
    "BCH": "Bitcoin Cash",
    "NEAR": "NEAR Protocol",
    "LEO": "LEO Token",
    "DAI": "Dai",
    "SUI": "Sui",
    "APT": "Aptos",
    "TON": "Toncoin",
}

PERIODS = {
    "30d": ("30d", "1d"),
    "90d": ("90d", "1d"),
    "180d": ("180d", "1d"),
    "1y": ("1y", "1d"),
    "max": ("max", "1wk"),
}

# -----------------------------
# DATA FETCHING (CACHED)
# -----------------------------
@cache.memoize(timeout=300)
def get_crypto_data(symbol: str, period: str = "90d"):
    ticker = f"{symbol}-USD"
    period_key, interval = PERIODS.get(period, PERIODS["90d"])
    
    try:
        df = yf.download(
            ticker,
            period=period_key,
            interval=interval,
            auto_adjust=True,
            progress=False,
            timeout=10
        )
        if df.empty:
            raise ValueError("No data")
        df = df.reset_index()
        df["EMA_12"] = df["Close"].ewm(span=12).mean()
        df["EMA_26"] = df["Close"].ewm(span=26).mean()
        df["EMA_50"] = df["Close"].ewm(span=50).mean()
        
        ema_fast = df["Close"].ewm(span=12).mean()
        ema_slow = df["Close"].ewm(span=26).mean()
        df["MACD"] = ema_fast - ema_slow
        df["MACD_Signal"] = df["MACD"].ewm(span=9).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]
        
        delta = df["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))
        
        return df
    except Exception as e:
        print(f"yfinance error for {symbol}: {e}")
        raise

def get_indicator_summary(df: pd.DataFrame):
    latest = df.iloc[-1]
    prev_5d = df.iloc[-6] if len(df) > 5 else df.iloc[0]
    
    return {
        'price': latest['Close'],
        'price_change_24h_pct': ((latest['Close'] - df.iloc[-2]['Close']) / df.iloc[-2]['Close']) * 100,
        'rsi': latest['RSI'],
        'rsi_change': latest['RSI'] - prev_5d['RSI'],
        'macd_hist': latest['MACD_Hist'],
        'macd_hist_change': latest['MACD_Hist'] - prev_5d['MACD_Hist'],
        'price_vs_ema50_pct': ((latest['Close'] - latest['EMA_50']) / latest['EMA_50']) * 100,
        'volume': latest['Volume'],
    }

# -----------------------------
# INTERACTIVE PLOTLY CHART
# -----------------------------
@cache.memoize(timeout=300)
def create_plotly_chart(symbol: str, period: str = "90d"):
    df = get_crypto_data(symbol, period)
    name = COINS.get(symbol, symbol)
    
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=("Price & EMAs", "MACD", "RSI", "Volume"),
        row_heights=[0.5, 0.15, 0.15, 0.2]
    )
    
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df['Date'],
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="Price"
    ), row=1, col=1)
    
    # EMAs
    for span, color in [(12, '#6366f1'), (26, '#f59e0b'), (50, '#10b981')]:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df[f'EMA_{span}'],
            name=f'EMA {span}', line=dict(color=color, width=2)
        ), row=1, col=1)
    
    # MACD
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name='MACD', line=dict(color='#3b82f6')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD_Signal'], name='Signal', line=dict(color='#ef4444')), row=2, col=1)
    fig.add_trace(go.Bar(x=df['Date'], y=df['MACD_Hist'], name='Histogram', marker_color='#8b5cf6'), row=2, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], name='RSI', line=dict(color='#a855f7')), row=3, col=1)
    for level, color in [(70, 'red'), (30, 'green')]:
        fig.add_hline(y=level, line_dash="dash", line_color=color, row=3, col=1)
    
    # Volume
    fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], name='Volume', marker_color='#94a3b8'), row=4, col=1)
    
    fig.update_layout(
        title=f"{name} ({symbol}-USD) • {period.upper()} Technical Analysis",
        xaxis_rangeslider_visible=False,
        height=900,
        template="plotly_dark" if request.args.get('dark') == 'true' else "plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_xaxes(title_text="Date", row=4, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1)
    fig.update_yaxes(title_text="Volume", row=4, col=1)
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

# -----------------------------
# AI ANALYSIS
# -----------------------------
@cache.memoize(timeout=600)
def get_ai_analysis(symbol: str, period: str, level: str = 'advanced'):
    if not ANTHROPIC_API_KEY:
        return "AI analysis unavailable (API key missing).", "N/A"
    
    try:
        df = get_crypto_data(symbol, period)
        ind = get_indicator_summary(df)
        confidence = "High" if abs(ind['rsi'] - 50) > 20 and abs(ind['macd_hist']) > 0.1 else "Medium"
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        prompt = f"""You are an expert crypto technical analyst providing educational insights on {COINS[symbol]} ({symbol}-USD).

Current Data ({period} view):
- Price: ${ind['price']:.2f} ({ind['price_change_24h_pct']:+.2f}% 24h)
- RSI: {ind['rsi']:.1f} (change: {ind['rsi_change']:+.2f})
- MACD Histogram: {ind['macd_hist']:.4f} (change: {ind['macd_hist_change']:+.4f})
- Price vs EMA-50: {ind['price_vs_ema50_pct']:+.2f}%

Provide a {level} analysis:
"""
        if level == "beginner":
            prompt += "Explain in simple terms: Is the trend positive, negative, or neutral? What do RSI and MACD suggest about momentum?"
        else:
            prompt += "Give a detailed technical breakdown: trend strength, momentum signals, key support/resistance via EMAs, and potential implications from recent indicator changes."

        prompt += "\n\nImportant: This is educational only. Never use words like buy, sell, target, or give trading advice."

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.content[0].text.strip(), confidence
    except Exception as e:
        print(f"AI Error: {e}")
        return "AI analysis temporarily unavailable.", "N/A"

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        symbol = "BTC"
    
    period = request.args.get("period", "90d")
    if period not in PERIODS:
        period = "90d"
    
    dark_mode = request.args.get("dark", "false") == "true"
    level = request.args.get("interpretation_level", "advanced")
    
    try:
        df = get_crypto_data(symbol, period)
        price = float(df["Close"].iloc[-1])
        analysis, confidence = get_ai_analysis(symbol, period, level)
        chart_html = create_plotly_chart(symbol, period)
    except:
        analysis = "Data temporarily unavailable. Please try again."
        confidence = "N/A"
        chart_html = "<p style='text-align:center; color:red;'>Chart failed to load.</p>"
        price = 0.0

    # Build selects
    coin_options = "".join(
        f'<option value="{k}" {"selected" if k==symbol else ""}>{v}</option>'
        for k, v in sorted(COINS.items(), key=lambda x: x[1])
    )
    
    period_options = "".join(
        f'<option value="{k}" {"selected" if k==period else ""}>{k.upper()}</option>'
        for k in PERIODS.keys()
    )
    
    return f"""
    <!DOCTYPE html>
    <html lang="en" data-theme="{'dark' if dark_mode else 'light'}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{COINS[symbol]} Dashboard</title>
        <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #f8fafc; --card: white; --text: #1e293b; --accent: #6366f1; }}
            [data-theme="dark"] {{ --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --accent: #818cf8; }}
            body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); padding: 20px; min-height: 100vh; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .header h1 {{ font-size: 2.8rem; font-weight: 700; }}
            .price {{ font-size: 2.2rem; font-weight: 600; color: #10b981; }}
            .controls {{ display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin: 20px 0; }}
            select, button {{ padding: 10px 16px; border-radius: 10px; border: 1px solid #cbd5e1; background: var(--card); color: var(--text); }}
            .card {{ background: var(--card); padding: 25px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); margin-bottom: 25px; }}
            .ai-card p {{ line-height: 1.8; font-size: 1.1rem; }}
            .confidence {{ background: var(--accent); color: white; padding: 6px 14px; border-radius: 20px; font-weight: 600; }}
            .disclaimer {{ background: #fef3c7; padding: 15px; border-radius: 10px; border-left: 4px solid #f59e0b; margin-top: 30px; }}
            .dark-toggle {{ cursor: pointer; font-size: 1.5rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📈 {COINS[symbol]} Crypto Dashboard</h1>
                <div class="price">${price:,.2f} USD</div>
                <div class="dark-toggle" onclick="toggleDark()">{'🌙' if not dark_mode else '☀️'}</div>
            </div>

            <div class="controls">
                <select onchange="window.location.href='?coin='+this.value+'&period={period}&dark={'true' if dark_mode else 'false'}'">{coin_options}</select>
                <select onchange="window.location.href='?coin={symbol}&period='+this.value+'&dark={'true' if dark_mode else 'false'}'">{period_options}</select>
                <select onchange="window.location.href='?coin={symbol}&period={period}&interpretation_level='+this.value+'&dark={'true' if dark_mode else 'false'}'">
                    <option value="beginner" {'selected' if level=='beginner' else ''}>Beginner</option>
                    <option value="advanced" {'selected' if level=='advanced' else ''}>Advanced</option>
                </select>
            </div>

            <div class="card ai-card">
                <h3>🤖 AI Technical Analysis <span class="confidence">Confidence: {confidence}</span></h3>
                <p>{analysis}</p>
            </div>

            <div class="card">
                <div>{chart_html}</div>
            </div>

            <div class="disclaimer">
                <strong>⚠️ Educational Purpose Only:</strong> This dashboard provides technical analysis for educational purposes. It is not financial advice. Cryptocurrency involves high risk.
            </div>
        </div>

        <script>
            function toggleDark() {{
                const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                const newTheme = isDark ? 'light' : 'dark';
                const params = new URLSearchParams(window.location.search);
                params.set('dark', newTheme === 'dark');
                window.location.search = params.toString();
            }}
        </script>
    </body>
    </html>
    """

@app.route("/api/ask", methods=["POST"])
@limiter.limit("15 per minute")
def ask_ai():
    # Same as before, but updated prompt for context
    data = request.get_json()
    question = data.get("question", "").strip()
    symbol = data.get("symbol", "BTC").upper()
    period = data.get("period", "90d")
    
    if not question or symbol not in COINS:
        return jsonify({"error": "Invalid request"}), 400
    
    try:
        df = get_crypto_data(symbol, period)
        ind = get_indicator_summary(df)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        prompt = f"""Educational crypto assistant answering user question about {COINS[symbol]}.

Current values:
Price: ${ind['price']:.2f}, RSI: {ind['rsi']:.1f}, MACD Hist: {ind['macd_hist']:.4f}

User question: {question}

Answer clearly, reference current values, avoid trading advice."""
        
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return jsonify({"answer": message.content[0].text})
    except:
        return jsonify({"error": "Failed to answer"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
