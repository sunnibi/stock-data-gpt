# get_stock_data.py
import yfinance as yf
import json
from datetime import datetime, timedelta
import os
import sys

def fetch_stock_data(ticker, market, days=60):
    end = datetime.now()
    start = end - timedelta(days=days)

    if market.lower() == "kr":
        ticker = f"{ticker}.KS"  # 한국 종목은 .KS 또는 .KQ 필요

    df = yf.download(ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
    df = df[['Close']].dropna().reset_index()

    new_prices = [
        {"date": row['Date'].strftime('%Y-%m-%d'), "close": round(row['Close'], 2)}
        for _, row in df.iterrows()
    ]

    # 저장 경로 설정
    #folder = f"data/{market.lower()}"
    #os.makedirs(folder, exist_ok=True)
    #path = f"{folder}/{ticker.replace('.KS','')}.json"
    folder = f"data/{market.lower()}"
    os.makedirs(folder, exist_ok=True)  # 폴더 없으면 생성
    path = f"{folder}/{ticker.replace('.KS','')}.json"
    
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
            old_dates = {item["date"] for item in existing.get("history", [])}
            new_prices = [p for p in new_prices if p["date"] not in old_dates]
            combined = existing["history"] + new_prices
    else:
        combined = new_prices

    output = {
        "ticker": ticker.replace(".KS", ""),
        "market": market.upper(),
        "updated": end.strftime('%Y-%m-%d'),
        "history": combined
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        os.system(f"touch {path}")
        
if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "TSLA"
    market = sys.argv[2] if len(sys.argv) > 2 else "us"
    fetch_stock_data(ticker, market)

