
# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    CategoricalParameter,
    BooleanParameter,
)
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class BBMarginStrategy(IStrategy):
    """
    Bollinger Bands Margin Strategy
    - Entry Long: Close < Lower Band
    - Entry Short: Close > Upper Band
    - Leverage: 30x
    - ROI: 10%
    - Stoploss: -1.0 (No stoploss)
    """

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = True

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    # ROI table:
    # 0 mins: 10%
    minimal_roi = {
        "0": 0.10
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -1.0

    # Trailing stop:
    trailing_stop = False

    # Run "populate_indicators" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    # DCA Settings
    position_adjustment_enable = True
    max_entry_position_adjustment = 20  # Reduced from 100 to prevent massive position size

    # Optional order type mapping.
    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }

    # Optional order time in force.
    order_time_in_force = {
        "entry": "gtc",
        "exit": "gtc"
    }

    def maximize_leverage(self, pair: str, current_time: datetime, current_rate: float,
                          proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                          **kwargs) -> float:
        return 30.0

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        return 30.0

    def adjust_trade_position(self, trade: 'Trade', current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float, max_stake: float,
                              **kwargs):
        """
        Custom trade adjustment logic, returning the stake amount that a trade should be increased.
        """
        # Add to position if current profit is below -50% (Widened from -30%)
        if current_profit > -0.50:
            return None

        # Check limit of adjustments (already handled by max_entry_position_adjustment but good to double check)
        if trade.nr_of_successful_entries >= self.max_entry_position_adjustment:
            return None

        # Determine the stake amount to add.
        # We want to add $3 cost. With leverage 30, that's $90 size.
        # But Freqtrade's stake_amount usually refers to the "cost" (margin used) in futures.
        # So we return the initial stake amount.
        return self.config['stake_amount']

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # EMA for Trend Filter
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['bb_lowerband']) &
                (dataframe['rsi'] < 30) &  # RSI Filter
                (dataframe['close'] > dataframe['ema_200']) &  # Trend Filter: Only Long in Uptrend
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['bb_upperband']) &
                (dataframe['rsi'] > 70) &  # RSI Filter
                (dataframe['close'] < dataframe['ema_200']) &  # Trend Filter: Only Short in Downtrend
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit Short if price crosses above EMA 200 (Trend changed to Up)
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema_200']) &
                (dataframe['volume'] > 0)
            ),
            'exit_short'] = 1

        # Exit Long if price crosses below EMA 200 (Trend changed to Down)
        # DISABLE for Longs to allow DCA recovery (Asymmetric Exit)
        # dataframe.loc[
        #     (
        #         (dataframe['close'] < dataframe['ema_200']) &
        #         (dataframe['volume'] > 0)
        #     ),
        #     'exit_long'] = 1
        
        return dataframe
