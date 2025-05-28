import yfinance as yf
import json
import os
import sys
from datetime import datetime, timedelta

input_ticker = sys.argv[1].upper()
market = sys.argv[2].upper() if len(sys.argv) > 2 else "US"

# 한국 종목 변환 (005930 → 005930.KS)
if market == "KR" and not input_ticker.endswith(".KS") and not input_ticker.endswith(".KQ"):
    if input_ticker.startswith("0") or input_ticker.startswith("1"):
        ticker = f"{input_ticker}.KS"
    else:
        ticker = f"{input_ticker}.KQ"
else:
    ticker = input_ticker

folder = f"data/{market.lower()}"
os.makedirs(folder, exist_ok=True)

end = datetime.now()
start = end - timedelta(days=60)

df = yf.download(ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
df = df[['Close']].dropna().reset_index()

prices = [
    {"date": row['Date'].strftime('%Y-%m-%d'), "close": round(row['Close'], 2)}
    for _, row in df.iterrows()
]

path = f"{folder}/{input_ticker}.json"  # 원래 티커명 기준 파일명
with open(path, "w", encoding="utf-8") as f:
    json.dump({
        "ticker": input_ticker,
        "market": market,
        "updated": end.strftime('%Y-%m-%d'),
        "history": prices
    }, f, indent=2)
