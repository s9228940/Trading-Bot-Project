from flask import Flask, send_file, request, jsonify
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
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

# Configure caching
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300
cache = Cache(app)

# Configure rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

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
# DATA + INDICATORS (CACHED)
# -----------------------------
@cache.memoize(timeout=300)
def get_crypto_data(symbol):
    end = datetime.now()
    start = end - timedelta(days=90)

    ticker = f"{symbol}-USD"
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            timeout=10
        )
    except Exception as e:
        print(f"Error downloading data: {e}")
        raise

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


def get_indicator_summary(df):
    """Get standardized indicator summary with trends"""
    latest = df.iloc[-1]
    prev_5d = df.iloc[-6] if len(df) > 5 else df.iloc[0]
    
    return {
        'price': latest['Close'],
        'rsi': latest['RSI'],
        'rsi_5d_change': latest['RSI'] - prev_5d['RSI'],
        'macd': latest['MACD'],
        'macd_signal': latest['MACD_Signal'],
        'macd_hist': latest['MACD_Hist'],
        'macd_hist_5d_change': latest['MACD_Hist'] - prev_5d['MACD_Hist'],
        'ema_12': latest['EMA_12'],
        'ema_26': latest['EMA_26'],
        'ema_50': latest['EMA_50'],
        'price_vs_ema50_pct': ((latest['Close'] - latest['EMA_50']) / latest['EMA_50']) * 100,
        'volume': latest['Volume']
    }


def calculate_confidence(indicators):
    """Calculate confidence level based on indicator alignment"""
    confidence_score = 0
    
    # RSI confidence (distance from neutral 50)
    rsi_distance = abs(indicators['rsi'] - 50)
    if rsi_distance > 30:
        confidence_score += 3
    elif rsi_distance > 15:
        confidence_score += 2
    else:
        confidence_score += 1
    
    # EMA alignment
    price = indicators['price']
    if (price > indicators['ema_12'] > indicators['ema_26'] > indicators['ema_50']) or \
       (price < indicators['ema_12'] < indicators['ema_26'] < indicators['ema_50']):
        confidence_score += 3
    elif (price > indicators['ema_50']) or (price < indicators['ema_50']):
        confidence_score += 2
    else:
        confidence_score += 1
    
    # MACD histogram magnitude
    if abs(indicators['macd_hist']) > abs(indicators['macd']) * 0.1:
        confidence_score += 2
    else:
        confidence_score += 1
    
    # Map to labels
    if confidence_score >= 7:
        return "High"
    elif confidence_score >= 5:
        return "Medium"
    else:
        return "Low"


# -----------------------------
# CHART (CACHED)
# -----------------------------
@cache.memoize(timeout=300)
def create_chart(symbol):
    df = get_crypto_data(symbol)
    name = COINS[symbol]
    indicators = get_indicator_summary(df)

    fig = plt.figure(figsize=(15, 12))
    fig.suptitle(f"{name} ({symbol}-USD) Technical Analysis", fontsize=16, fontweight='bold')

    ax1 = plt.subplot(4, 1, 1)
    ax1.plot(df.index, df["Close"], label="Close", color="black", linewidth=2)
    ax1.plot(df.index, df["EMA_12"], label="EMA 12", alpha=0.7)
    ax1.plot(df.index, df["EMA_26"], label="EMA 26", alpha=0.7)
    ax1.plot(df.index, df["EMA_50"], label="EMA 50", alpha=0.7)
    
    # Add trend annotation
    if indicators['price'] > indicators['ema_50']:
        trend_text = "Short-term: Bullish"
        trend_color = "green"
    else:
        trend_text = "Short-term: Bearish"
        trend_color = "red"
    ax1.text(0.02, 0.95, trend_text, transform=ax1.transAxes, 
             fontsize=10, verticalalignment='top', 
             bbox=dict(boxstyle='round', facecolor=trend_color, alpha=0.3))
    
    ax1.set_ylabel("Price (USD)", fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(alpha=0.3)

    ax2 = plt.subplot(4, 1, 2)
    ax2.plot(df.index, df["MACD"], label="MACD", linewidth=2)
    ax2.plot(df.index, df["MACD_Signal"], label="Signal", linewidth=2)
    colors = ['green' if x > 0 else 'red' for x in df["MACD_Hist"]]
    ax2.bar(df.index, df["MACD_Hist"], alpha=0.4, color=colors, label="Histogram")
    ax2.axhline(0, color="black", linestyle="--", linewidth=1)
    ax2.set_ylabel("MACD", fontweight='bold')
    ax2.legend(loc='upper left')
    ax2.grid(alpha=0.3)

    ax3 = plt.subplot(4, 1, 3)
    ax3.plot(df.index, df["RSI"], color="purple", linewidth=2, label="RSI")
    
    # Highlight overbought/oversold zones
    ax3.axhspan(70, 100, alpha=0.2, color='red', label='Overbought Zone')
    ax3.axhspan(0, 30, alpha=0.2, color='green', label='Oversold Zone')
    ax3.axhline(70, color="red", linestyle="--", linewidth=1)
    ax3.axhline(30, color="green", linestyle="--", linewidth=1)
    ax3.axhline(50, color="gray", linestyle=":", linewidth=1, alpha=0.5)
    
    ax3.set_ylim(0, 100)
    ax3.set_ylabel("RSI", fontweight='bold')
    ax3.legend(loc='upper left')
    ax3.grid(alpha=0.3)

    ax4 = plt.subplot(4, 1, 4)
    ax4.bar(df.index, df["Volume"], alpha=0.6, color="blue")
    ax4.set_ylabel("Volume", fontweight='bold')
    ax4.grid(alpha=0.3)

    for ax in [ax1, ax2, ax3, ax4]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read(), df


# -----------------------------
# AI ANALYSIS (CACHED)
# -----------------------------
@cache.memoize(timeout=600)
def get_ai_analysis(symbol, interpretation_level='advanced'):
    """Get AI analysis with timeout and confidence"""
    if not ANTHROPIC_API_KEY:
        return "AI analysis unavailable: API key not configured.", "N/A"
    
    try:
        df = get_crypto_data(symbol)
        indicators = get_indicator_summary(df)
        confidence = calculate_confidence(indicators)
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=15.0)
        
        prev = df.iloc[-2]
        price_change = ((indicators['price'] - prev["Close"]) / prev["Close"]) * 100
        
        prompt_base = f"""Analyze this cryptocurrency technical data for {COINS[symbol]} ({symbol}):

Current Price: ${indicators['price']:.2f} (24h change: {price_change:+.2f}%)

Technical Indicators & Trends:
- RSI: {indicators['rsi']:.2f} (5-day change: {indicators['rsi_5d_change']:+.2f})
- MACD: {indicators['macd']:.4f}
- MACD Signal: {indicators['macd_signal']:.4f}
- MACD Histogram: {indicators['macd_hist']:.4f} (5-day change: {indicators['macd_hist_5d_change']:+.4f})
- Price vs EMA-50: {indicators['price_vs_ema50_pct']:+.2f}%
- EMA Alignment: 12=${indicators['ema_12']:.2f}, 26=${indicators['ema_26']:.2f}, 50=${indicators['ema_50']:.2f}

"""

        if interpretation_level == 'beginner':
            prompt_base += """Provide a simple explanation (2-3 sentences) of what these indicators mean in plain English. 
Focus on whether the market sentiment appears positive, negative, or neutral. Avoid jargon.

IMPORTANT: This is educational analysis only, not financial advice. Do not use words like "buy", "sell", or "target price"."""
        else:
            prompt_base += """Provide a technical analysis (3-4 sentences) covering:
1. Overall trend based on indicator alignment
2. Momentum signals from RSI and MACD trends
3. Key observations from the 5-day changes

IMPORTANT: This is educational analysis only, not financial advice. Focus on interpretation, not trading recommendations."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt_base}]
        )
        
        analysis = message.content[0].text
        return analysis, confidence
        
    except anthropic.TimeoutError:
        return "AI analysis temporarily unavailable (timeout). Please try again.", "N/A"
    except Exception as e:
        print(f"AI Error: {e}")
        return "AI analysis temporarily unavailable. Please try again.", "N/A"


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        symbol = "BTC"

    interpretation_level = request.args.get('interpretation_level', 'advanced')

    df = get_crypto_data(symbol)
    price = float(df["Close"].iloc[-1])
    
    analysis, confidence = get_ai_analysis(symbol, interpretation_level)

    options = "".join(
        f'<option value="{k}" {"selected" if k==symbol else ""}>{v}</option>'
        for k, v in COINS.items()
    )

    interpretation_select = f"""
        <option value="beginner" {"selected" if interpretation_level=="beginner" else ""}>Beginner</option>
        <option value="advanced" {"selected" if interpretation_level=="advanced" else ""}>Advanced</option>
    """

    example_questions = [
        "What does MACD mean?",
        "Is momentum strengthening?",
        "Is RSI signaling overbought conditions?",
        "What do the EMAs suggest?",
        "Should I be concerned about the current RSI?"
    ]

    example_buttons = "".join([
        f'<button class="example-btn" onclick="document.getElementById(\'ai-question\').value=\'{q}\'; askAI();">{q}</button>'
        for q in example_questions
    ])

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{COINS[symbol]} Crypto Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .header {{
                text-align: center;
                color: white;
                margin-bottom: 30px;
            }}
            
            .header h1 {{
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            }}
            
            .price-display {{
                font-size: 2rem;
                font-weight: 600;
                color: #4ade80;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
            }}
            
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            
            .controls {{
                display: flex;
                justify-content: center;
                gap: 30px;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }}
            
            .control-group {{
                display: flex;
                flex-direction: column;
                gap: 8px;
            }}
            
            .control-group label {{
                font-weight: 600;
                color: #374151;
                font-size: 0.9rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            select {{
                padding: 12px 20px;
                font-size: 16px;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                background: white;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.3s;
            }}
            
            select:hover {{
                border-color: #667eea;
            }}
            
            select:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            .info-card {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 15px;
                margin-bottom: 25px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .info-card h3 {{
                font-size: 1.3rem;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            
            .confidence-badge {{
                display: inline-block;
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: 600;
                background: rgba(255,255,255,0.2);
                backdrop-filter: blur(10px);
            }}
            
            .info-card p {{
                line-height: 1.8;
                font-size: 1.05rem;
            }}
            
            .question-card {{
                background: #f9fafb;
                border: 2px solid #e5e7eb;
                padding: 25px;
                border-radius: 15px;
                margin-bottom: 25px;
            }}
            
            .question-card h3 {{
                color: #1f2937;
                font-size: 1.3rem;
                margin-bottom: 10px;
            }}
            
            .question-card .subtitle {{
                color: #6b7280;
                margin-bottom: 20px;
            }}
            
            .input-group {{
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }}
            
            .question-input {{
                flex: 1;
                padding: 14px 18px;
                font-size: 16px;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                font-family: inherit;
                transition: all 0.3s;
            }}
            
            .question-input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            .ask-button {{
                padding: 14px 35px;
                font-size: 16px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.3s;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .ask-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0,0,0,0.15);
            }}
            
            .ask-button:disabled {{
                background: #9ca3af;
                cursor: not-allowed;
                transform: none;
            }}
            
            .example-questions {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 15px;
            }}
            
            .example-btn {{
                padding: 8px 16px;
                background: white;
                border: 2px solid #e5e7eb;
                border-radius: 20px;
                cursor: pointer;
                font-size: 0.9rem;
                transition: all 0.3s;
                font-family: inherit;
            }}
            
            .example-btn:hover {{
                background: #667eea;
                color: white;
                border-color: #667eea;
            }}
            
            .answer-box {{
                background: white;
                border: 2px solid #667eea;
                padding: 20px;
                border-radius: 10px;
                margin-top: 15px;
                display: none;
            }}
            
            .answer-box.show {{
                display: block;
                animation: slideIn 0.3s ease;
            }}
            
            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translateY(-10px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
            
            .loading {{
                color: #667eea;
                font-style: italic;
            }}
            
            .chart-container {{
                margin-top: 30px;
                border-radius: 15px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .chart-container img {{
                width: 100%;
                height: auto;
                display: block;
            }}
            
            .disclaimer {{
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 15px 20px;
                border-radius: 10px;
                margin-top: 20px;
                font-size: 0.9rem;
                color: #92400e;
            }}
            
            .tooltip {{
                position: relative;
                display: inline-block;
                cursor: help;
                color: #667eea;
            }}
            
            @media (max-width: 768px) {{
                .header h1 {{
                    font-size: 1.8rem;
                }}
                .price-display {{
                    font-size: 1.5rem;
                }}
                .container {{
                    padding: 20px;
                }}
                .controls {{
                    flex-direction: column;
                    gap: 15px;
                }}
                .input-group {{
                    flex-direction: column;
                }}
            }}
        </style>
        <script>
            async function askAI() {{
                const question = document.getElementById('ai-question').value.trim();
                const answerBox = document.getElementById('answer-box');
                const answerText = document.getElementById('answer-text');
                const askButton = document.getElementById('ask-button');
                
                if (!question) {{
                    alert('Please enter a question!');
                    return;
                }}
                
                askButton.disabled = true;
                answerBox.classList.add('show');
                answerText.innerHTML = '<span class="loading">🤔 Thinking...</span>';
                
                try {{
                    const response = await fetch('/api/ask', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{question: question, symbol: '{symbol}'}})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.error) {{
                        answerText.innerHTML = '<strong style="color: #dc2626;">Error:</strong> ' + data.error;
                    }} else {{
                        answerText.innerHTML = '<strong>Answer:</strong> ' + data.answer;
                    }}
                }} catch (error) {{
                    answerText.innerHTML = '<strong style="color: #dc2626;">Error:</strong> Failed to get answer. Please try again.';
                }} finally {{
                    askButton.disabled = false;
                }}
            }}
            
            document.addEventListener('DOMContentLoaded', function() {{
                document.getElementById('ai-question').addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') askAI();
                }});
            }});
        </script>
    </head>
    <body>
        <div class="header">
            <h1>📈 {COINS[symbol]} Dashboard</h1>
            <div class="price-display">${price:,.2f} USD</div>
        </div>
        
        <div class="container">
            <div class="controls">
                <div class="control-group">
                    <label for="coin">Cryptocurrency</label>
                    <form method="get" style="margin: 0;">
                        <select name="coin" id="coin" onchange="this.form.submit()">
                            {options}
                        </select>
                        <input type="hidden" name="interpretation_level" value="{interpretation_level}">
                    </form>
                </div>
                <div class="control-group">
                    <label for="interpretation_level">Analysis Level</label>
                    <form method="get" style="margin: 0;">
                        <select name="interpretation_level" id="interpretation_level" onchange="this.form.submit()">
                            {interpretation_select}
                        </select>
                        <input type="hidden" name="coin" value="{symbol}">
                    </form>
                </div>
            </div>

            <div class="info-card">
                <h3>
                    🤖 AI Technical Analysis
                    <span class="confidence-badge">Confidence: {confidence}</span>
                </h3>
                <p>{analysis}</p>
            </div>

            <div class="question-card">
                <h3>💬 Ask AI Questions</h3>
                <p class="subtitle">Get instant explanations about technical indicators and chart patterns</p>
                
                <div class="example-questions">
                    <small style="width: 100%; display: block; margin-bottom: 8px; color: #6b7280; font-weight: 600;">Quick questions:</small>
                    {example_buttons}
                </div>
                
                <div class="input-group">
                    <input 
                        type="text" 
                        id="ai-question" 
                        class="question-input" 
                        placeholder="Type your question here..."
                    />
                    <button id="ask-button" class="ask-button" onclick="askAI()">Ask AI</button>
                </div>
                
                <div id="answer-box" class="answer-box">
                    <div id="answer-text"></div>
                </div>
            </div>

            <div class="chart-container">
                <img src="/chart?coin={symbol}" alt="{COINS[symbol]} Technical Analysis Chart"/>
            </div>

            <div class="disclaimer">
                <strong>⚠️ Educational Purpose Only:</strong> This analysis is for educational purposes only and does not constitute financial advice. AI may not always have up-to-date information. Cryptocurrency trading carries significant risk. Always do your own research and consult with a financial advisor before making investment decisions.
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/chart")
def chart():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        return "Invalid coin", 400

    try:
        img_bytes, _ = create_chart(symbol)
        return send_file(io.BytesIO(img_bytes), mimetype="image/png")
    except Exception as e:
        print(f"Error creating chart: {e}")
        return f"Error generating chart: {str(e)}", 500


@app.route("/api/analysis")
def api_analysis():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        return jsonify({"error": "Invalid coin"}), 400
    
    interpretation_level = request.args.get('interpretation_level', 'advanced')
    
    df = get_crypto_data(symbol)
    analysis, confidence = get_ai_analysis(symbol, interpretation_level)
    
    return jsonify({
        "symbol": symbol,
        "name": COINS[symbol],
        "analysis": analysis,
        "confidence": confidence,
        "interpretation_level": interpretation_level
    })


@app.route("/api/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask_ai():
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "API key not configured"}), 500
    
    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        symbol = data.get("symbol", "BTC").upper()
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        df = get_crypto_data(symbol)
        indicators = get_indicator_summary(df)
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=10.0)
        
        prompt = f"""You are a helpful cryptocurrency education assistant. The user is viewing {COINS[symbol]} ({symbol}) technical charts.

Current market context:
- Price: ${indicators['price']:.2f}
- RSI: {indicators['rsi']:.2f} (5-day change: {indicators['rsi_5d_change']:+.2f})
- MACD Histogram: {indicators['macd_hist']:.4f}
- Price vs EMA-50: {indicators['price_vs_ema50_pct']:+.2f}%

User question: {question}

Provide a clear, educational answer (2-4 sentences). When explaining indicators:
- Reference the current chart values
- Use phrases like "On the RSI panel..." or "Looking at the price chart..."
- Explain concepts in context

IMPORTANT: This is educational only. Avoid trading recommendations. Do not use "buy", "sell", or "target" language."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return jsonify({
            "answer": message.content[0].text,
            "question": question
        })
        
    except anthropic.TimeoutError:
        return jsonify({"error": "Request timed out. Please try again."}), 504
    except Exception as e:
        print(f"Ask AI Error: {e}")
        return jsonify({"error": "Failed to process question. Please try again."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
