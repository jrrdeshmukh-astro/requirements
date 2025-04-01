#!/usr/bin/env python3
import os
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# -------------------------------
# CONFIGURATION
# -------------------------------

# Base settings for the index simulation
BASE_DATE = "2024-04-01"  # Must be within the past 365 days available via free API
BASE_VALUE = 100          # Starting portfolio value (index value)
TARGET_WEIGHT = 0.20      # 20% for each asset (equal weighting for 5 assets)
THRESHOLD = 0.05          # Rebalance if any asset's weight deviates more than 5% from target

# VIX settings (index for volatility)
VIX_THRESHOLD = 20      # Rebalance when VIX > 20
VIX_BUFFER = 0.04       # Buffer to revert to equal weighting when VIX drops below 20

# Mapping: symbol -> CoinGecko coin id
COIN_IDS = {
    "BTC": "bitcoin",
    "LTC": "litecoin",
    "ETH": "ethereum",
    "XRP": "ripple",
    "USDT": "tether"
}

# -------------------------------
# FUNCTIONS
# -------------------------------

def fetch_price_data_from_csv(symbol):
    """
    Load the saved coin data from CSV files.
    """
    filename = f"{symbol}_price_data.csv"
    if os.path.exists(filename):
        df = pd.read_csv(filename, parse_dates=['Date'], index_col='Date')
        print(f"Loaded data for {symbol} from {filename}")
        return df
    else:
        print(f"Error: {filename} not found. Please ensure the data has been saved.")
        return None

def fetch_vix_data_from_csv():
    """
    Fetch historical VIX data from the CSV provided by CBOE.
    Returns a DataFrame with Date as index and the VIX closing price.
    """
    vix_url = "VIX_History.csv"
    vix_data = pd.read_csv(vix_url)
    
    # Process the data
    vix_data['Date'] = pd.to_datetime(vix_data['DATE'])
    vix_data.set_index('Date', inplace=True)
    vix_data.rename(columns={'CLOSE': 'VIX'}, inplace=True)  # Assuming the column name is 'VIX Close'
    
    return vix_data['VIX']

def save_weights_to_csv(weights, filename="portfolio_weights.csv"):
    """
    Save the portfolio weights to a CSV file.
    """
    weights_df = pd.DataFrame([weights])  # Convert dictionary to a DataFrame
    weights_df.index = [str(weights_df.index[0])]  # Use the current date as the index (convert it to string)
    weights_df.to_csv(filename, mode='a', header=not os.path.exists(filename))  # Append data to the file
    print(f"Portfolio weights saved to {filename}")


def save_to_csv(df, filename):
    """
    Save the DataFrame to a CSV file.
    """
    df.to_csv(filename)
    print(f"Data saved to {filename}")

def simulate_rebalanced_portfolio(prices_df, vix_series, base_date, base_value, target_weight, threshold, vix_threshold, vix_buffer):
    """
    Simulate a portfolio starting at base_date with base_value and equal-weighted holdings.
    Rebalance the portfolio if either:
      - any asset deviates more than the threshold from its target weight, OR
      - the daily VIX exceeds the vix_threshold.
    
    When VIX > vix_threshold, rebalancing targets a high-volatility allocation:
      - USDT gets 50% of the portfolio,
      - Each of the other assets gets 12.5% (i.e. (1 - 0.50)/4).
    Otherwise, use the normal equal-weight target for all assets, with a 4% buffer before switching.
    
    Returns: a Series of portfolio values indexed by date, a list of rebalancing dates, and a list of weights.
    """
    # Initialize holdings based on base date prices using normal equal weighting
    base_prices = prices_df.loc[base_date]
    holdings = {}
    for coin in prices_df.columns:
        holdings[coin] = (base_value * target_weight) / base_prices[coin]
    
    portfolio_values = {}
    rebalancing_dates = []
    weights_history = []  # List to store weights at each rebalance
    prev_vix_above_threshold = False

    # Iterate over each day from base_date onward
    for current_date, row in prices_df.iterrows():
        if current_date < base_date:
            continue
        
        # Compute current portfolio value and weights
        current_value = 0
        current_weights = {}
        for coin in prices_df.columns:
            coin_value = holdings[coin] * row[coin]
            current_value += coin_value
            current_weights[coin] = coin_value  # temporary value; will normalize next
        
        for coin in current_weights:
            current_weights[coin] /= current_value
        
        # Determine current target weights based on VIX:
        # If VIX exceeds threshold, assign 50% to USDT and 12.5% to others.
        current_vix = vix_series.get(current_date, 0)
        if current_vix > vix_threshold:
            new_target_weights = {coin: (0.50 if coin == "USDT" else 0.125) for coin in prices_df.columns}
            vix_trigger = True
        else:
            new_target_weights = {coin: target_weight for coin in prices_df.columns}
            vix_trigger = False
        
        # If the VIX is below the threshold and there was a previous VIX > 20 state, check for buffer
        if not vix_trigger and prev_vix_above_threshold:
            weight_deviation = any(abs(current_weights[coin] - target_weight) > threshold for coin in current_weights)
            if not weight_deviation:  # If the weight deviation is small enough, revert to equal-weight
                rebalancing_dates.append(current_date)
                prev_vix_above_threshold = False
                continue
        
        # If VIX exceeded threshold, keep it in high-volatility allocation until buffer check
        if vix_trigger:
            prev_vix_above_threshold = True

        # Check if any asset's weight deviates more than the threshold from the new target
        weight_deviation = any(abs(current_weights[coin] - new_target_weights[coin]) > threshold for coin in current_weights)
        
        if weight_deviation or vix_trigger:
            # Rebalance: update holdings to new target weights using current portfolio value
            for coin in prices_df.columns:
                holdings[coin] = (current_value * new_target_weights[coin]) / row[coin]
            rebalancing_dates.append(current_date)
            
            # Save current portfolio weights to the list
            weights_history.append(current_weights)
            save_weights_to_csv(current_weights)  # Save to CSV after rebalancing
        
        portfolio_values[current_date] = current_value

    portfolio_series = pd.Series(portfolio_values)
    return portfolio_series, rebalancing_dates, weights_history

def compute_performance_stats(portfolio_series):
    """
    Compute performance statistics from a portfolio value series.
    Returns a dictionary with annualized return, volatility, Sharpe ratio, and maximum drawdown.
    """
    daily_returns = portfolio_series.pct_change().dropna()
    days = (portfolio_series.index[-1] - portfolio_series.index[0]).days
    cagr = (portfolio_series.iloc[-1] / portfolio_series.iloc[0]) ** (365/days) - 1
    volatility = daily_returns.std() * np.sqrt(365)
    sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365)
    running_max = portfolio_series.cummax()
    drawdowns = (portfolio_series - running_max) / running_max
    max_drawdown = drawdowns.min()
    
    stats = {
        "CAGR (Annualized Return)": cagr,
        "Annualized Volatility": volatility,
        "Sharpe Ratio": sharpe_ratio,
        "Maximum Drawdown": max_drawdown
    }
    return stats

def main():
    # Fetch price data for each coin from saved CSVs and merge into a single DataFrame on Date index
    dfs = []
    for symbol in COIN_IDS.keys():
        print(f"Loading data for {symbol}...")
        df = fetch_price_data_from_csv(symbol)
        if df is not None:
            dfs.append(df[[symbol]])  # Adding each coin's data to the list
        
    prices_df = pd.concat(dfs, axis=1).sort_index()

    # Convert BASE_DATE to a datetime object and filter data accordingly
    base_date = pd.to_datetime(BASE_DATE)  # Convert to datetime object
    prices_df = prices_df[prices_df.index >= base_date]  # Now comparison will work
    
    if base_date not in prices_df.index:
        base_date = prices_df.index[0]
        print(f"Base date not found; using first available date: {base_date}")

    # Fetch VIX data from the CSV file provided by CBOE
    print(f"Fetching VIX data from CSV for date range {base_date} to {prices_df.index[-1]}...")
    vix_series = fetch_vix_data_from_csv()
    
    # Calculate the correlation between BTC and VIX
    btc_vix_corr = prices_df["BTC"].pct_change().corr(vix_series.pct_change())
    print(f"\nCorrelation between BTC and VIX: {btc_vix_corr:.2f}")

    # Simulate portfolio with rebalancing using a 5% threshold or VIX > threshold trigger
    portfolio_series, rebalancing_dates, weights_history = simulate_rebalanced_portfolio(
        prices_df, vix_series, base_date, BASE_VALUE, TARGET_WEIGHT, THRESHOLD, VIX_THRESHOLD, VIX_BUFFER
    )
    
    # Compute performance statistics
    stats = compute_performance_stats(portfolio_series)
    
    # Print performance stats
    print("\nHODL Index (Rebalanced with VIX Trigger) Performance Statistics:")
    for key, value in stats.items():
        if "Return" in key or "Drawdown" in key:
            print(f"{key}: {value*100:.2f}%")
        else:
            print(f"{key}: {value:.2f}")
    
    print("\nRebalancing executed on the following dates:")
    for date in rebalancing_dates:
        print(date)
    
    # Plot the portfolio value over time
    plt.figure(figsize=(10, 6))
    plt.plot(portfolio_series.index, portfolio_series, label="Rebalanced HODL Index")
    plt.title("HODL Index with 5% Weight & VIX (>20) Rebalancing Trigger\n(50% in USDT if VIX > 20)")
    plt.xlabel("Date")
    plt.ylabel("Portfolio Value (Index)")

    # Adding performance stats to the chart
    stats_text = '\n'.join([f"{key}: {value*100:.2f}%" if "Return" in key or "Drawdown" in key else f"{key}: {value:.2f}" for key, value in stats.items()])
    plt.text(0.95, 0.05, stats_text, ha='right', va='bottom', transform=plt.gca().transAxes, fontsize=10, bbox=dict(facecolor='white', alpha=0.7))

    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    main()

