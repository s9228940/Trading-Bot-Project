# app.py
from flask import Flask, send_file, render_template_string
import matplotlib
matplotlib.use("Agg")  # Needed for Render (no GUI)
import matplotlib.pyplot as plt
import yfinance as yf
import pandas as pd
import io
import datetime as dt

app = Flask(__name__)

def generate_chart():
    """Fetches Bitcoin data, generates chart, returns PNG as bytes."""
    end_date = dt.datetime.now()
    start_date = end_date - dt.timedelta(days=180)

    data = yf.download("BTC-USD", start=start_date, end=end_date)

    if data.empty:
        raise ValueError("No data returned from Yahoo Finance")

    closes = data["Close"]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(closes.index, closes.values)
    ax.set_title("Bitcoin Closing Price (Last 180 Days)")
    ax.set_ylabel("Price (USD)")
    ax.set_xlabel("Date")

    # Save to bytes buffer
    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img_bytes.seek(0)
    return img_bytes


@app.route("/")
def index():
    """Main page showing chart + last price."""
    end_date = dt.datetime.now()
    data = yf.download("BTC-USD", period="1d")

    if data.empty:
        last_price = "Unavailable"
    else:
        last_price = float(data["Close"].iloc[-1])

    # Inline HTML template
    html = f"""
    <html>
    <head>
        <title>Bitcoin Dashboard</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                text-align: center;
            }}
            img {{
                margin-top: 20px;
                border: 2px solid #444;
            }}
        </style>
    </head>
    <body>
        <h1>Bitcoin Price Dashboard</h1>
        <h2>Latest Price: ${last_price:,.2f}</h2>
        <img src="/chart" />
    </body>
    </html>
    """
    return html


@app.route("/chart")
def chart():
    """Returns chart PNG."""
    try:
        img = generate_chart()
        return send_file(img, mimetype="image/png")
    except Exception as e:
        return f"Error generating chart: {str(e)}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
