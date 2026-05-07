from typing import Dict, Any

from pandas import DataFrame
from freqtrade.strategy import IStrategy
import talib.abstract as ta
from freqtrade.vendor.qtpylib import indicators as qtpylib


class PodcastAlphaStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '1m'
    stoploss = -0.025
    can_short = False

    minimal_roi: Dict[str, float] = {
        "0": 0.0
    }

    startup_candle_count: int = 82

    short_sma_window = 23
    long_sma_window = 82

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict[str, Any]) -> DataFrame:
        dataframe['sma_short'] = ta.SMA(dataframe, timeperiod=self.short_sma_window)
        dataframe['sma_long'] = ta.SMA(dataframe, timeperiod=self.long_sma_window)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict[str, Any]) -> DataFrame:
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['sma_short'], dataframe['sma_long']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict[str, Any]) -> DataFrame:
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['sma_short'], dataframe['sma_long']) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'
        ] = 1

        return dataframe