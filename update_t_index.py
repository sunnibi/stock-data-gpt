# update_t_index.py
import json
import os
import sys

T_JSON_PATH = "T.JSON"
BASE_URL = "https://sunnibi.github.io/stock-data-gpt/data"

def update_index(ticker, market):
    index = {}
    if os.path.exists(T_JSON_PATH):
        with open(T_JSON_PATH, "r", encoding="utf-8") as f:
            index = json.load(f)

    # URL 생성
    url = f"{BASE_URL}/{market.lower()}/{ticker.upper()}.json"
    index[ticker.upper()] = url

    with open(T_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

if __name__ == "__main__":
    ticker = sys.argv[1]
    market = sys.argv[2]
    update_index(ticker, market)
