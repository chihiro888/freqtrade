import subprocess
import json
import re
import sys
from datetime import datetime
import time

def run_command(command, description):
    print(f"--- {description} ---")
    try:
        # Using shell=True for complex commands with pipes or redirects
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing {description}: {e}")
        # Only print stderr if it's not a generic Freqtrade error (keep logs clean)
        # print(f"Stdout: {e.stdout}") 
        # print(f"Stderr: {e.stderr}")
        return None

def extract_metrics(output, month_name):
    try:
        # Try English Regex first
        net_profit_match = re.search(r'│\s+Net Profit\s+│\s+([-\d\.]+)\s+USDT', output)
        if not net_profit_match:
            # Try Korean Regex
            net_profit_match = re.search(r'│\s+순수익금\s+│\s+([-\d\.]+)\s+USDT', output)
        net_profit = net_profit_match.group(1) if net_profit_match else "N/A"

        profit_pct_match = re.search(r'│\s+Tot Profit\s+%\s+│\s+([-\d\.]+)%', output)
        if not profit_pct_match:
             profit_pct_match = re.search(r'│\s+총 수익률 %\s+│\s+([-\d\.]+)%', output)
        profit_pct = profit_pct_match.group(1) if profit_pct_match else "N/A"

        drawdown_match = re.search(r'│\s+Drawdown\s+│\s+([-\d\.]+)\s+USDT\s+\(([\d\.]+)%\)', output)
        if not drawdown_match:
            drawdown_match = re.search(r'│\s+절대 낙폭\(Drawdown\)\s+│\s+([-\d\.]+)\s+USDT\s+\(([\d\.]+)%\)', output)
        
        drawdown_usdt = drawdown_match.group(1) if drawdown_match else "N/A"
        drawdown_pct = drawdown_match.group(2) if drawdown_match else "N/A"

        # Trade Count
        trades_match = re.search(r'│\s+Total/Daily Avg Trades\s+│\s+(\d+)\s+/', output)
        if not trades_match:
            trades_match = re.search(r'│\s+총 거래수 / 일평균\s+│\s+(\d+)\s+/', output)
        trade_count = trades_match.group(1) if trades_match else "N/A"

        return {
            "Month": month_name,
            "Profit %": profit_pct,
            "Profit USDT": net_profit,
            "Drawdown %": drawdown_pct,
            "Trades": trade_count
        }
    except Exception as e:
        print(f"Failed to parse metrics for {month_name}: {e}")
        return {
            "Month": month_name,
            "Profit %": "Error",
            "Profit USDT": "Error",
            "Drawdown %": "Error"
        }

months = [
    ("20250101-20250131", "Jan 2025"),
    ("20250201-20250228", "Feb 2025"),
    ("20250301-20250331", "Mar 2025"),
    ("20250401-20250430", "Apr 2025"),
    ("20250501-20250531", "May 2025"),
    ("20250601-20250630", "Jun 2025"),
    ("20250701-20250731", "Jul 2025"),
    ("20250801-20250831", "Aug 2025"),
    ("20250901-20250930", "Sep 2025"),
    ("20251001-20251031", "Oct 2025"),
    ("20251101-20251130", "Nov 2025"),
    ("20251201-20251231", "Dec 2025"),
]

results = []

print("Starting Monthly Backtest for 2025...")
print("Strategy: BBMarginStrategy (Asymmetric Exit)")

for timerange, month_name in months:
    print(f"\nProcessing {month_name} ({timerange})...")
    
    # 1. Download Data
    dl_cmd = f"export PYTHONHTTPSVERIFY=0 && .venv/bin/freqtrade download-data --config config.json --config futures_config.json --timerange {timerange} --pairs XRP/USDT:USDT --prepend"
    dl_output = run_command(dl_cmd, f"Download Data {month_name}")
    
    if dl_output is None:
        # If download failed but data might exist, try running backtest anyway?
        # But based on previous logs, download prints stdout even on success.
        # Check if output contains "Downloaded data"
        pass

    # 2. Run Backtest
    bt_cmd = f".venv/bin/freqtrade backtesting --config config.json --config futures_config.json --strategy BBMarginStrategy --timerange {timerange} --pairs XRP/USDT:USDT"
    bt_output = run_command(bt_cmd, f"Backtest {month_name}")

    if bt_output:
        metrics = extract_metrics(bt_output, month_name)
        results.append(metrics)
        print(f"Result {month_name}: {metrics}")
    else:
        results.append({"Month": month_name, "Profit %": "Fail", "Profit USDT": "Fail", "Drawdown %": "Fail"})

# Print Summary Table
print("\n" + "="*65)
print("Monthly Backtest Results (2025)")
print("="*65)
print(f"{'Month':<10} | {'Profit %':<10} | {'Profit $':<10} | {'MDD %':<10} | {'Trades':<8}")
print("-" * 65)
for r in results:
    print(f"{r['Month']:<10} | {r['Profit %']:<10} | {r['Profit USDT']:<10} | {r['Drawdown %']:<10} | {r['Trades']:<8}")
print("="*65)
