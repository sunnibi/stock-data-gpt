# get_stock_data.py
import yfinance as yf
import json
import os
import sys
from datetime import datetime, timedelta, date as DateObject

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
        if input_ticker.endswith((".KS", ".KQ")):
            yfinance_ticker = input_ticker
        else:
            is_kr_market_no_suffix = True
            if input_ticker.startswith(("0", "1")):
                yfinance_ticker = f"{input_ticker}.KS"
                alternative_yfinance_ticker = f"{input_ticker}.KQ"
            else:
                yfinance_ticker = f"{input_ticker}.KQ"
                alternative_yfinance_ticker = f"{input_ticker}.KS"
    else: # US or other markets
        yfinance_ticker = input_ticker
    
    if not yfinance_ticker: # Should not happen if logic above is correct
        print(f"Error: Could not determine yfinance ticker for {input_ticker} ({market})")
        sys.exit(1)

    # 3. Prepare file path and determine fetch range (for incremental update)
    folder_path = f"data/{market.lower()}"
    os.makedirs(folder_path, exist_ok=True)
    file_path = f"{folder_path}/{base_ticker_for_output}.json"

    existing_history_map = {} # Date string to price entry map for easy merge
    start_date_for_fetch = current_processing_time - timedelta(days=num_days_default) # Default full fetch

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            
            # Validate basic structure and market match
            if not isinstance(existing_data, dict) or \
               existing_data.get("ticker") != base_ticker_for_output or \
               existing_data.get("market") != market:
                print(f"Warning: Existing file {file_path} seems to be for a different stock/market or corrupted. Performing full fetch.")
                # Fallback to full fetch by not modifying start_date_for_fetch or existing_history_map
            else:
                temp_existing_history = existing_data.get("history", [])
                if temp_existing_history: # If there's actual history
                    # Build a map for efficient lookup and update
                    for entry in temp_existing_history:
                        existing_history_map[entry['date']] = entry

                    last_date_str = temp_existing_history[-1]['date'] # Assumes sorted
                    last_date_dt = datetime.strptime(last_date_str, DATE_FORMAT)
                    
                    # Fetch data starting from the day AFTER the last recorded date
                    start_date_for_fetch = last_date_dt + timedelta(days=1)
                    
                    if start_date_for_fetch.date() > current_processing_time.date():
                        print(f"Data for {base_ticker_for_output} ({market}) is already up to date as of {last_date_str}.")
                        sys.exit(0) # Exit gracefully, no new data needed
                    print(f"Existing data found for {base_ticker_for_output}. Last entry: {last_date_str}. Fetching new data from {start_date_for_fetch.strftime(DATE_FORMAT)}.")
                else: # File exists but no history entries
                    print(f"Existing file {file_path} found but no history. Performing full fetch for {num_days_default} days.")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error reading or parsing existing file {file_path}: {e}. Performing full fetch for {num_days_default} days.")
            existing_history_map = {} # Reset on error
            # start_date_for_fetch remains the default full fetch duration
    else:
        print(f"No existing data file found for {base_ticker_for_output}. Performing full fetch for {num_days_default} days.")

    # 4. Data Fetching with yfinance (with retry for KR stocks)
    df = None
    final_yfinance_ticker_used = yfinance_ticker # Store the ticker that successfully fetches data

    print(f"Attempt 1: Downloading data for {yfinance_ticker} from {start_date_for_fetch.strftime(DATE_FORMAT)} to {current_processing_time.strftime(DATE_FORMAT)}")
    try:
        df_temp = yf.download(yfinance_ticker, 
                              start=start_date_for_fetch.strftime(DATE_FORMAT), 
                              end=current_processing_time.strftime(DATE_FORMAT), # Fetch up to current day
                              progress=False)
        if not df_temp.empty:
            df = df_temp
        else:
            print(f"No data returned for {yfinance_ticker} (empty DataFrame on first try).")
    except Exception as e:
        print(f"Failed to download data for {yfinance_ticker} on first try: {e}")

    if df is None and is_kr_market_no_suffix and alternative_yfinance_ticker:
        print(f"First attempt failed for KR ticker {input_ticker}. Trying alternative: {alternative_yfinance_ticker}")
        final_yfinance_ticker_used = alternative_yfinance_ticker
        print(f"Attempt 2: Downloading data for {alternative_yfinance_ticker} from {start_date_for_fetch.strftime(DATE_FORMAT)} to {current_processing_time.strftime(DATE_FORMAT)}")
        try:
            df_temp = yf.download(alternative_yfinance_ticker, 
                                  start=start_date_for_fetch.strftime(DATE_FORMAT), 
                                  end=current_processing_time.strftime(DATE_FORMAT),
                                  progress=False)
            if not df_temp.empty:
                df = df_temp
                print(f"Successfully fetched data with alternative ticker: {alternative_yfinance_ticker}")
            else:
                print(f"No data returned for {alternative_yfinance_ticker} (empty DataFrame on second try).")
        except Exception as e:
            print(f"Failed to download data for {alternative_yfinance_ticker} on second try: {e}")

    if df is None or df.empty:
        print(f"Could not retrieve new data for {base_ticker_for_output} ({market}) after all attempts. Check ticker and market validity or data availability for the period.")
        # If existing data was loaded, we might choose to save it back without new entries,
        # or exit with error if the goal is always to fetch new data.
        # For now, if no NEW data, and existing_history_map is empty, it's a hard fail.
        if not existing_history_map:
             sys.exit(1)
        else: # Only existing data available, no new data fetched
             print("No new data fetched. Saving existing data if any.")
             new_prices = [] # Ensure new_prices is empty
    else:
        print(f"Successfully downloaded data using {final_yfinance_ticker_used}.")
        df = df[['Close']].dropna().reset_index()
        if df.empty:
            print(f"No 'Close' price data available for {final_yfinance_ticker_used} after processing. Using existing data if any.")
            new_prices = []
        else:
            new_prices = [
                {"date": row['Date'].strftime(DATE_FORMAT), "close": round(row['Close'], 2)}
                for _, row in df.iterrows()
            ]
    
    # 5. Merge new data with existing history
    for price_entry in new_prices:
        existing_history_map[price_entry['date']] = price_entry
    
    combined_history = sorted(list(existing_history_map.values()), key=lambda x: x['date'])

    if not combined_history and not new_prices: # Still no history after all attempts
        print(f"No historical data could be compiled for {base_ticker_for_output}. Aborting file save.")
        sys.exit(1)
        
    # 6. Prepare and save output
    output_data = {
        "ticker": base_ticker_for_output,
        "market": market,
        "yfinance_ticker_used": final_yfinance_ticker_used, # Record which yfinance ticker was successful
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
