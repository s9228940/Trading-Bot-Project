from flask import Flask, send_file, request, jsonify
from flask_caching import Cache
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
from functools import lru_cache
import hashlib

app = Flask(__name__)

# Configure caching
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes
cache = Cache(app)

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
@cache.memoize(timeout=300)  # Cache for 5 minutes
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


# -----------------------------
# CHART (CACHED)
# -----------------------------
@cache.memoize(timeout=300)  # Cache for 5 minutes
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
    return buf.read(), df  # Return bytes instead of BytesIO


# -----------------------------
# AI ANALYSIS (CACHED)
# -----------------------------
@cache.memoize(timeout=600)  # Cache for 10 minutes (AI responses change less)
def get_ai_analysis(symbol, interpretation_level='advanced'):
    """Get AI analysis of the technical indicators"""
    if not ANTHROPIC_API_KEY:
        return "AI analysis unavailable: API key not configured. Please set ANTHROPIC_API_KEY environment variable."
    
    try:
        df = get_crypto_data(symbol)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Calculate trends
        price_change = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100
        
        prompt_template = """Analyze this cryptocurrency technical data for {name} ({symbol}):

Current Price: ${current_price:.2f}
24h Change: {price_change:.2f}%

Technical Indicators:
- EMA 12: ${ema_12:.2f}
- EMA 26: ${ema_26:.2f}
- EMA 50: ${ema_50:.2f}
- MACD: {macd:.4f}
- MACD Signal: {macd_signal:.4f}
- MACD Histogram: {macd_hist:.4f}
- RSI: {rsi:.2f}

"""

        if interpretation_level == 'beginner':
            prompt_template += "Provide a very simple and brief explanation (2-3 sentences) of the current market sentiment based on the indicators, suitable for a beginner. Explain what RSI and MACD are in simple terms. Avoid complex jargon and focus on a clear bullish/bearish/neutral outlook."
        else:  # Default to advanced
            prompt_template += "Provide a brief technical analysis (3-4 sentences) covering:\n1. Overall trend (bullish/bearish/neutral)\n2. What the indicators suggest\n3. Key support/resistance levels if relevant\nKeep it concise and actionable."

        prompt = prompt_template.format(
            name=COINS[symbol],
            symbol=symbol,
            current_price=latest['Close'],
            price_change=price_change,
            ema_12=latest['EMA_12'],
            ema_26=latest['EMA_26'],
            ema_50=latest['EMA_50'],
            macd=latest['MACD'],
            macd_signal=latest['MACD_Signal'],
            macd_hist=latest['MACD_Hist'],
            rsi=latest['RSI']
        )

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

    interpretation_level = request.args.get('interpretation_level', 'advanced')

    df = get_crypto_data(symbol)
    price = float(df["Close"].iloc[-1])
    
    # Get AI analysis (now cached)
    analysis = get_ai_analysis(symbol, interpretation_level)

    options = "".join(
        f'<option value="{k}" {"selected" if k==symbol else ""}>{v}</option>'
        for k, v in COINS.items()
    )

    interpretation_options = [
        {'value': 'beginner', 'label': 'Beginner'},
        {'value': 'advanced', 'label': 'Advanced'}
    ]

    interpretation_select = "".join(
        f'<option value="{opt["value"]}" {"selected" if opt["value"]==interpretation_level else ""}>{opt["label"]}</option>'
        for opt in interpretation_options
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
                margin: 10px 5px;
            }}
            select:hover {{
                background: #f0f0f0;
            }}
            label {{
                font-weight: bold;
                margin-right: 5px;
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
            .question-box {{
                background: #e3f2fd;
                border-left: 4px solid #2196F3;
                padding: 20px;
                margin: 20px 0;
                text-align: left;
                border-radius: 5px;
            }}
            .question-box h3 {{
                margin-top: 0;
                color: #1565C0;
            }}
            .question-input {{
                width: calc(100% - 120px);
                padding: 12px;
                font-size: 16px;
                border: 2px solid #2196F3;
                border-radius: 5px;
                margin-right: 10px;
            }}
            .ask-button {{
                padding: 12px 30px;
                font-size: 16px;
                background: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
            }}
            .ask-button:hover {{
                background: #1976D2;
            }}
            .ask-button:disabled {{
                background: #ccc;
                cursor: not-allowed;
            }}
            .answer-box {{
                background: #fff;
                border: 1px solid #2196F3;
                padding: 15px;
                margin-top: 15px;
                border-radius: 5px;
                text-align: left;
                display: none;
            }}
            .answer-box.show {{
                display: block;
            }}
            .loading {{
                color: #666;
                font-style: italic;
            }}
            img {{
                max-width: 100%;
                height: auto;
                margin-top: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            .controls {{
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 20px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }}
            .control-group {{
                display: flex;
                align-items: center;
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
                
                // Show loading state
                askButton.disabled = true;
                answerBox.classList.add('show');
                answerText.innerHTML = '<span class="loading">🤔 Thinking...</span>';
                
                try {{
                    const response = await fetch('/api/ask', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{
                            question: question,
                            symbol: '{symbol}'
                        }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.error) {{
                        answerText.innerHTML = '<strong style="color: #d32f2f;">Error:</strong> ' + data.error;
                    }} else {{
                        answerText.innerHTML = '<strong>Answer:</strong> ' + data.answer;
                    }}
                }} catch (error) {{
                    answerText.innerHTML = '<strong style="color: #d32f2f;">Error:</strong> Failed to get answer. Please try again.';
                }} finally {{
                    askButton.disabled = false;
                }}
            }}
            
            // Allow Enter key to submit
            document.addEventListener('DOMContentLoaded', function() {{
                document.getElementById('ai-question').addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') {{
                        askAI();
                    }}
                }});
            }});
        </script>
    </head>
    <body>
        <div class="container">
            <h1>{COINS[symbol]} Dashboard</h1>
            <h2>Current Price: ${price:,.2f}</h2>

            <div class="controls">
                <div class="control-group">
                    <form method="get" style="display: inline-block;">
                        <label for="coin">Cryptocurrency:</label>
                        <select name="coin" id="coin" onchange="this.form.submit()">
                            {options}
                        </select>
                        <input type="hidden" name="interpretation_level" value="{interpretation_level}">
                    </form>
                </div>
                <div class="control-group">
                    <form method="get" style="display: inline-block;">
                        <label for="interpretation_level">Analysis Level:</label>
                        <select name="interpretation_level" id="interpretation_level" onchange="this.form.submit()">
                            {interpretation_select}
                        </select>
                        <input type="hidden" name="coin" value="{symbol}">
                    </form>
                </div>
            </div>

            <div class="analysis-box">
                <h3>🤖 AI Technical Analysis ({interpretation_level.capitalize()})</h3>
                <p>{analysis}</p>
            </div>

            <div class="question-box">
                <h3>💬 Ask AI Questions</h3>
                <p style="margin-bottom: 15px; color: #666;">Ask about technical indicators (MACD, RSI, EMA), trading strategies, or anything about the charts!</p>
                <div style="display: flex; align-items: center;">
                    <input 
                        type="text" 
                        id="ai-question" 
                        class="question-input" 
                        placeholder="e.g., What does MACD mean? or Is this a good time to buy?"
                    />
                    <button id="ask-button" class="ask-button" onclick="askAI()">Ask</button>
                </div>
                <div id="answer-box" class="answer-box">
                    <div id="answer-text"></div>
                </div>
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

    try:
        img_bytes, _ = create_chart(symbol)
        return send_file(io.BytesIO(img_bytes), mimetype="image/png")
    except Exception as e:
        print(f"Error creating chart: {e}")
        return f"Error generating chart: {str(e)}", 500


@app.route("/api/analysis")
def api_analysis():
    """API endpoint for getting just the analysis"""
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        return jsonify({"error": "Invalid coin"}), 400
    
    interpretation_level = request.args.get('interpretation_level', 'advanced')
    
    df = get_crypto_data(symbol)
    analysis = get_ai_analysis(symbol, interpretation_level)
    
    return jsonify({
        "symbol": symbol,
        "name": COINS[symbol],
        "analysis": analysis,
        "interpretation_level": interpretation_level
    })


@app.route("/api/ask", methods=["POST"])
def ask_ai():
    """API endpoint for asking AI questions"""
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "API key not configured"}), 500
    
    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        symbol = data.get("symbol", "BTC").upper()
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        # Get current data for context
        df = get_crypto_data(symbol)
        latest = df.iloc[-1]
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        prompt = f"""You are a helpful cryptocurrency trading assistant. The user is looking at technical analysis charts for {COINS[symbol]} ({symbol}).

Current context:
- Price: ${latest['Close']:.2f}
- RSI: {latest['RSI']:.2f}
- MACD: {latest['MACD']:.4f}
- EMA 12: ${latest['EMA_12']:.2f}
- EMA 26: ${latest['EMA_26']:.2f}
- EMA 50: ${latest['EMA_50']:.2f}

User question: {question}

Provide a clear, concise answer (2-4 sentences). If they're asking about a technical indicator, explain what it means and how to interpret it in the context of {COINS[symbol]}'s current data."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return jsonify({
            "answer": message.content[0].text,
            "question": question
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # This is only for local development
    # Gunicorn doesn't use this block
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
