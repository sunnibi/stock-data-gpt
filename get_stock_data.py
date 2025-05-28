# get_stock_data.py
import yfinance as yf
import json
import os
import sys
from datetime import datetime, timedelta

# --- Configuration & Constants ---
ALLOWED_MARKETS = {"US", "KR"}
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def fetch_stock_data_logic(input_ticker_orig, market_orig, num_days_default=60):
    input_ticker = input_ticker_orig.upper()
    market = market_orig.upper()
    current_processing_time = datetime.now()

    # 1. Validate market code
    if market not in ALLOWED_MARKETS:
        print(f"Error: Invalid market code '{market}'. Allowed markets are: {', '.join(ALLOWED_MARKETS)}")
        sys.exit(1)

    # 2. Determine yfinance ticker and original ticker for filename
    yfinance_ticker = None
    alternative_yfinance_ticker = None
    is_kr_market_no_suffix = False
    # 파일명 및 JSON 내 'ticker' 필드에 사용될 접미사 없는 순수 티커
    base_ticker_for_output = input_ticker.replace(".KS", "").replace(".KQ", "")


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
    
    if not yfinance_ticker: # 로직상 발생하기 어렵지만 방어 코드
        print(f"Error: Could not determine yfinance ticker for {input_ticker} ({market})")
        sys.exit(1)

    # 3. Prepare file path and determine fetch range (for incremental update)
    folder_path = f"data/{market.lower()}"
    os.makedirs(folder_path, exist_ok=True)
    file_path = f"{folder_path}/{base_ticker_for_output}.json"

    existing_history_map = {} # Date string to price entry map for easy merge
    # 기본적으로 num_days_default 만큼의 데이터를 가져오도록 시작 날짜 설정
    start_date_for_fetch = current_processing_time - timedelta(days=num_days_default)

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            
            # 파일 내용 검증 (올바른 티커/마켓 정보, history 존재 여부)
            if not isinstance(existing_data, dict) or \
               existing_data.get("ticker") != base_ticker_for_output or \
               existing_data.get("market") != market:
                print(f"Warning: Existing file {file_path} metadata mismatch or corrupted. Performing full fetch for {num_days_default} days.")
                # start_date_for_fetch는 이미 num_days_default 기준으로 설정되어 있음
            else:
                temp_existing_history = existing_data.get("history", [])
                if temp_existing_history: # 실제 history 데이터가 있을 경우
                    # 날짜 기준으로 정렬되어 있다고 가정하고 마지막 날짜 사용
                    # (만약을 위해 로드 후 정렬하는 로직을 추가하는 것도 좋음)
                    for entry in temp_existing_history:
                        existing_history_map[entry['date']] = entry # 기존 데이터를 맵에 저장

                    last_date_str = temp_existing_history[-1]['date'] # 마지막 기록된 날짜
                    last_date_dt = datetime.strptime(last_date_str, DATE_FORMAT)
                    
                    # 마지막 기록된 날짜의 다음 날부터 데이터 가져오도록 시작 날짜 조정
                    start_date_for_fetch = last_date_dt + timedelta(days=1)
                    
                    # 만약 계산된 시작 날짜가 오늘 이후라면 (이미 최신 데이터)
                    if start_date_for_fetch.date() > current_processing_time.date():
                        print(f"Data for {base_ticker_for_output} ({market}) is already up to date as of {last_date_str}. No new data to fetch.")
                        sys.exit(0) # 정상 종료
                    print(f"Existing data found for {base_ticker_for_output}. Last entry: {last_date_str}. Fetching new data from {start_date_for_fetch.strftime(DATE_FORMAT)}.")
                else: # 파일은 있으나 history가 비어있는 경우
                    print(f"Existing file {file_path} found but no history. Performing full fetch for {num_days_default} days.")
        except (json.JSONDecodeError, KeyError, ValueError) as e: # 파일 읽기/파싱 오류
            print(f"Error reading or parsing existing file {file_path}: {e}. Performing full fetch for {num_days_default} days.")
            existing_history_map = {} # 오류 시 기존 데이터 사용 안 함
            # start_date_for_fetch는 이미 num_days_default 기준으로 설정되어 있음
    else: # 기존 파일이 없는 경우
        print(f"No existing data file found for {base_ticker_for_output}. Performing full fetch for {num_days_default} days.")

    # 4. Data Fetching with yfinance (with retry for KR stocks)
    df = None
    final_yfinance_ticker_used = yfinance_ticker # 실제 성공한 yfinance 티커 기록용

    print(f"Attempt 1: Downloading data for {yfinance_ticker} from {start_date_for_fetch.strftime(DATE_FORMAT)} to {current_processing_time.strftime(DATE_FORMAT)}")
    try:
        # `progress=False` 인자 제거됨
        df_temp = yf.download(yfinance_ticker, 
                              start=start_date_for_fetch.strftime(DATE_FORMAT), 
                              end=current_processing_time.strftime(DATE_FORMAT))
        if not df_temp.empty:
            df = df_temp
        else:
            print(f"No data returned for {yfinance_ticker} (empty DataFrame on first try).")
    except Exception as e:
        print(f"Failed to download data for {yfinance_ticker} on first try: {e}")

    # 첫 시도 실패 & 한국 시장 & 사용자가 접미사 없이 티커 입력한 경우 -> 다른 접미사로 재시도
    if df is None and is_kr_market_no_suffix and alternative_yfinance_ticker:
        print(f"First attempt failed for KR ticker {input_ticker}. Trying alternative: {alternative_yfinance_ticker}")
        final_yfinance_ticker_used = alternative_yfinance_ticker # 재시도 티커로 업데이트
        print(f"Attempt 2: Downloading data for {alternative_yfinance_ticker} from {start_date_for_fetch.strftime(DATE_FORMAT)} to {current_processing_time.strftime(DATE_FORMAT)}")
        try:
            # `progress=False` 인자 제거됨
            df_temp = yf.download(alternative_yfinance_ticker, 
                                  start=start_date_for_fetch.strftime(DATE_FORMAT), 
                                  end=current_processing_time.strftime(DATE_FORMAT))
            if not df_temp.empty:
                df = df_temp
                print(f"Successfully fetched data with alternative ticker: {alternative_yfinance_ticker}")
            else:
                print(f"No data returned for {alternative_yfinance_ticker} (empty DataFrame on second try).")
        except Exception as e:
            print(f"Failed to download data for {alternative_yfinance_ticker} on second try: {e}")

    new_prices = [] # 새로 가져온 가격 정보를 담을 리스트
    if df is None or df.empty:
        print(f"Could not retrieve new data for {base_ticker_for_output} ({market}) after all attempts. Check ticker and market validity or data availability for the period.")
        # 새 데이터를 가져오지 못했고, 기존 데이터도 없다면 오류로 종료
        if not existing_history_map:
             sys.exit(1)
        # 새 데이터를 못 가져왔지만 기존 데이터는 있다면, 기존 데이터만 저장 (아래에서 처리)
        print("No new data fetched. Using existing data if any.")
    else:
        print(f"Successfully downloaded data using {final_yfinance_ticker_used}.")
        df = df[['Close']].dropna().reset_index()
        if df.empty:
            print(f"No 'Close' price data available for {final_yfinance_ticker_used} after processing. Using existing data if any.")
        else:
            new_prices = [
                {"date": row['Date'].strftime(DATE_FORMAT), "close": round(row['Close'], 2)}
                for _, row in df.iterrows()
            ]
    
    # 5. Merge new data with existing history (using the map for de-duplication and update)
    for price_entry in new_prices:
        existing_history_map[price_entry['date']] = price_entry # 새 데이터로 덮어쓰거나 추가
    
    # 맵의 값들(value)을 리스트로 변환 후 날짜 기준으로 정렬
    combined_history = sorted(list(existing_history_map.values()), key=lambda x: x['date'])

    if not combined_history: # 모든 시도 후에도 최종 데이터가 없다면
        print(f"No historical data could be compiled for {base_ticker_for_output}. Aborting file save.")
        sys.exit(1)
        
    # 6. Prepare and save output
    output_data = {
        "ticker": base_ticker_for_output,
        "market": market,
        "yfinance_ticker_used": final_yfinance_ticker_used,
        "updated": current_processing_time.strftime(DATETIME_FORMAT),
        "history": combined_history
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Successfully saved data to {file_path}")
    except Exception as e:
        print(f"Error writing data to {file_path}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_stock_data.py <TICKER_SYMBOL> [MARKET_CODE] [NUM_DAYS]")
        print("Example (US): python get_stock_data.py AAPL US 90")
        print("Example (KR): python get_stock_data.py 005930 KR") # num_days will use default
        sys.exit(1)

    cli_ticker = sys.argv[1]
    cli_market = sys.argv[2] if len(sys.argv) > 2 else "US"
    cli_num_days = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    
    fetch_stock_data_logic(cli_ticker, cli_market, cli_num_days)
