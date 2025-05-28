# get_stock_data.py
import yfinance as yf
import json
import os
import sys
from datetime import datetime, timedelta

ticker = sys.argv[1].upper()
folder = "data/us"
os.makedirs(folder, exist_ok=True)

end = datetime.now()
start = end - timedelta(days=60)

df = yf.download(ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
df = df[['Close']].dropna().reset_index()

prices = [
    {"date": row['Date'].strftime('%Y-%m-%d'), "close": round(row['Close'], 2)}
    for _, row in df.iterrows()
]

path = f"{folder}/{ticker}.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump({
        "ticker": ticker,
        "updated": end.strftime('%Y-%m-%d'),
        "history": prices
    }, f, indent=2)

