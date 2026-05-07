import ccxt
import pandas as pd
import time
import os

def fetch_year_data(exchange, symbol, year, timeframe='1m'):
    start_time_str = f'{year}-01-01T00:00:00Z'
    end_time_str = f'{year+1}-01-01T00:00:00Z'
    
    start_time = exchange.parse8601(start_time_str)
    end_time = exchange.parse8601(end_time_str)
    
    # Check if end_time is in the future
    now = exchange.milliseconds()
    if end_time > now:
        end_time = now

    if start_time > now:
        print(f"Skipping {year} for {symbol} as it is in the future.")
        return

    asset_name = symbol.split('/')[0].replace(':', '_') # Handle futures if any
    output_dir = 'Data/Binance'
    os.makedirs(output_dir, exist_ok=True)
    output_file = f'{output_dir}/{asset_name}_{timeframe}_{year}.parquet'
    
    if os.path.exists(output_file):
        print(f"File {output_file} already exists. Skipping.")
        return

    all_ohlcv = []
    current_time = start_time

    print(f"\n--- Fetching {symbol} {timeframe} data for {year} ---")

    # Timeframe to milliseconds mapping (simple version)
    tf_ms = {
        '1m': 60000,
        '5m': 300000,
        '15m': 900000,
        '1h': 3600000,
        '4h': 14400000,
        '1d': 86400000
    }.get(timeframe, 60000)

    while current_time < end_time:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_time, limit=1000)
            
            if not ohlcv:
                break
                
            # Filter out candles beyond the end_time boundary
            ohlcv = [candle for candle in ohlcv if candle[0] < end_time]
            
            if not ohlcv:
                break
                
            all_ohlcv.extend(ohlcv)
            
            last_time = ohlcv[-1][0]
            current_time = last_time + tf_ms 
            
            if len(all_ohlcv) % 10000 < 1000:
                print(f"  [{asset_name} {year}] Fetched {len(all_ohlcv)} candles... Current date: {exchange.iso8601(last_time)}")
                
        except Exception as e:
            print(f"Error fetching data: {e}")
            time.sleep(5)

    if not all_ohlcv:
        print(f"No data found for {symbol} in {year}.")
        return

    print(f"Finished fetching {symbol} {year}. Total candles: {len(all_ohlcv)}")

    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.drop_duplicates(subset=['timestamp'])
    
    df.to_parquet(output_file, index=False)
    print(f"✅ Saved to {output_file} ({len(df)} rows)")

import argparse

def main():
    parser = argparse.ArgumentParser(description="Mass historical data ingestion from Binance via CCXT.")
    parser.add_argument("--assets", nargs="+", default=["BNB/USDT", "BTC/USDT", "ETH/USDT"],
                        help="List of symbols to fetch (e.g. BTC/USDT ETH/USDT)")
    parser.add_argument("--years", nargs="+", type=int, default=[2021, 2022, 2023, 2024, 2025, 2026],
                        help="Years to fetch")
    parser.add_argument("--timeframe", type=str, default="1m", help="Timeframe to fetch (1m, 5m, 1h, etc.)")
    args = parser.parse_args()

    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    
    # Ensure symbols have /USDT if not provided
    assets = [a if '/' in a else f"{a}/USDT" for a in args.assets]

    for symbol in assets:
        for year in args.years:
            fetch_year_data(exchange, symbol, year, timeframe=args.timeframe)
            
    print("\n🎉 Mass historical data ingestion complete! All Parquet files saved to Data/Binance/")

if __name__ == "__main__":
    main()
