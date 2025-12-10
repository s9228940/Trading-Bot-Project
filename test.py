# test.py
from flask import Flask, send_file
import matplotlib
matplotlib.use("Agg")  # Required for Render (no display server)
import matplotlib.pyplot as plt
import yfinance as yf
import pandas as pd
import datetime as dt
import io

app = Flask(__name__)

# ---------------------------------------------------------------------
# Fetch price safely (handles MultiIndex, Series, empty data)
# ---------------------------------------------------------------------
def get_safe_price():
    data = yf.download("BTC-USD", period="1d", progress=False)

    if data.empty or "Close" not in data.columns:
        return "Unavailable"

    last_close = data["Close"].iloc[-1]

    # Fix: sometimes Yahoo returns a Series (MultiIndex)
    if isinstance(last_close, pd.Series):
        last_close = last_close.iloc[0]

    last_close = float(last_close)
    return f"${last_close:,.2f}"


# ---------------------------------------------------------------------
# Generate Price Chart
# ---------------------------------------------------------------------
def generate_chart():
    end = dt.datetime.now()
    start = end - dt.timedelta(days=180)

    # Must download 180-day data for chart
    data = yf.download("BTC-USD", start=start, end=end, progress=False)

    if data.empty:
        raise ValueError("No data returned from Yahoo Finance")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(data.index, data["Close"], linewidth=1.5)
    ax.set_title("Bitcoin Closing Price (Last 180 Days)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (USD)")

    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img_bytes.seek(0)
    return img_bytes


# ---------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------
@app.route("/")
def index():
    price = get_safe_price()

    html = f"""
    <html>
    <head>
        <title>Bitcoin Dashboard</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                text-align: center;
                margin: 40px;
            }}
            img {{
                border: 2px solid #555;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <h1>Bitcoin Dashboard</h1>
        <h2>Latest Price: {price}</h2>
        <img src="/chart" />
    </body>
    </html>
    """
    return html


# ---------------------------------------------------------------------
# Chart endpoint
# ---------------------------------------------------------------------
@app.route("/chart")
def chart():
    try:
        image = generate_chart()
        return send_file(image, mimetype="image/png")
    except Exception as e:
        return f"Error: {str(e)}", 500


# ---------------------------------------------------------------------
# Run app
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
