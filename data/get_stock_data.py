# get_stock_data.py
import yfinance as yf
import json
from datetime import datetime, timedelta

def fetch_stock_data(ticker="TSLA", days=60):
    end = datetime.now()
    start = end - timedelta(days=days)
    df = yf.download(ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
    df = df[['Close']].dropna().reset_index()

    prices = [
        {"date": row['Date'].strftime('%Y-%m-%d'), "close": round(row['Close'], 2)}
        for _, row in df.iterrows()
    ]

    return {
        "ticker": ticker,
        "updated": end.strftime('%Y-%m-%d'),
        "prices": prices
    }

# 저장 위치: data/stock.json
with open("data/stock.json", "w", encoding="utf-8") as f:
    json.dump(fetch_stock_data("TSLA"), f, ensure_ascii=False, indent=2)
