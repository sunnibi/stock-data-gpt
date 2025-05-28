# get_stock_data.py
import yfinance as yf
import json
import os
import sys
from datetime import datetime, timedelta

# --- Script Arguments ---
if len(sys.argv) < 2:
    print("Usage: python get_stock_data.py <TICKER_SYMBOL> [MARKET_CODE]")
    print("Example (US): python get_stock_data.py AAPL US")
    print("Example (KR): python get_stock_data.py 005930 KR")
    sys.exit(1)

input_ticker = sys.argv[1].upper()
# 시장 코드가 제공되지 않으면 기본값 'US' 사용
market = sys.argv[2].upper() if len(sys.argv) > 2 else "US"

# --- Ticker Symbol Determination for yfinance ---
yfinance_ticker = None
alternative_yfinance_ticker = None # 한국 시장 재시도용
is_kr_market_no_suffix = False

if market == "KR":
    if input_ticker.endswith((".KS", ".KQ")): # 튜플로 여러 접미사 동시 확인
        yfinance_ticker = input_ticker
    else:
        is_kr_market_no_suffix = True # 한국 시장이며, 사용자가 접미사를 입력하지 않음
        # KOSPI 종목 코드가 보통 '0' 또는 '1'로 시작하는 경향을 이용한 추론
        if input_ticker.startswith(("0", "1")): # 튜플로 여러 시작 문자 동시 확인
            yfinance_ticker = f"{input_ticker}.KS"
            alternative_yfinance_ticker = f"{input_ticker}.KQ"
        else:
            yfinance_ticker = f"{input_ticker}.KQ"
            alternative_yfinance_ticker = f"{input_ticker}.KS"
else: # US 또는 기타 시장
    yfinance_ticker = input_ticker

# --- Data Fetching ---
df = None
end_date = datetime.now()
start_date = end_date - timedelta(days=60) # 최근 60일 데이터

print(f"Attempting to download data for: {yfinance_ticker} (Market: {market})")
try:
    df_temp = yf.download(yfinance_ticker, 
                          start=start_date.strftime('%Y-%m-%d'), 
                          end=end_date.strftime('%Y-%m-%d'),
                          progress=False) # 다운로드 진행 표시 끔
    if not df_temp.empty:
        df = df_temp
    else:
        print(f"No data found for {yfinance_ticker} (empty DataFrame on first try).")
except Exception as e:
    print(f"Failed to download data for {yfinance_ticker} on first try: {e}")

# 첫 시도 실패 & 한국 시장 & 사용자가 접미사 없이 티커 입력한 경우 -> 다른 접미사로 재시도
if df is None and is_kr_market_no_suffix and alternative_yfinance_ticker:
    print(f"First attempt failed for {input_ticker} ({market}). Trying alternative: {alternative_yfinance_ticker}")
    try:
        df_temp = yf.download(alternative_yfinance_ticker, 
                              start=start_date.strftime('%Y-%m-%d'), 
                              end=end_date.strftime('%Y-%m-%d'),
                              progress=False)
        if not df_temp.empty:
            df = df_temp
            yfinance_ticker = alternative_yfinance_ticker # 성공한 티커로 업데이트
            print(f"Successfully fetched data with alternative ticker: {yfinance_ticker}")
        else:
            print(f"No data found for {alternative_yfinance_ticker} (empty DataFrame on second try).")
    except Exception as e:
        print(f"Failed to download data for {alternative_yfinance_ticker} on second try: {e}")

# 모든 시도 후에도 데이터가 없는 경우 스크립트 종료
if df is None or df.empty:
    print(f"Could not retrieve data for input ticker '{input_ticker}' (Market: {market}) after all attempts.")
    sys.exit(1) # 오류 코드로 종료

print(f"Successfully downloaded data for {yfinance_ticker}.")

# --- Data Processing ---
df = df[['Close']].dropna().reset_index()
if df.empty: # 혹시 모를 Close 데이터 부재 상황 대비
    print(f"No 'Close' price data available for {yfinance_ticker} after processing.")
    sys.exit(1)

prices = [
    {"date": row['Date'].strftime('%Y-%m-%d'), "close": round(row['Close'], 2)}
    for _, row in df.iterrows()
]

# --- File Saving ---
# 파일명은 사용자가 입력한 원본 티커명 기준 (예: 005930)
folder_path = f"data/{market.lower()}"
os.makedirs(folder_path, exist_ok=True)
file_path = f"{folder_path}/{input_ticker}.json"

output_data = {
    "ticker": input_ticker, # 사용자가 입력한 원본 티커
    "market": market,       # 사용자가 입력했거나 추론된 시장 코드
    "yfinance_ticker_used": yfinance_ticker, # 실제 yfinance 호출에 사용된 티커
    "updated": end_date.strftime('%Y-%m-%d %H:%M:%S'), # 업데이트 시각을 좀 더 정확히
    "history": prices
}

try:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        f.write("\n") # JSON 파일 끝에 개행 추가 (선택 사항)
    print(f"Successfully saved data to {file_path}")
except Exception as e:
    print(f"Error writing data to {file_path}: {e}")
    sys.exit(1)
