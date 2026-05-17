"""
Application settings loaded from environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConnectionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IB_")

    host: str = "127.0.0.1"
    port: int = 4002
    client_id: int = 17
    mode: Literal["paper", "live"] = "paper"


class UniverseSettings(BaseSettings):
    universe_size: int = 500
    min_price: float = 5.0
    adv_lookback_days: int = 20
    seed_csv: Path = Path(__file__).parent.parent / "data" / "seed_universe.csv"
    universe_refresh_days: int = 7


class IndicatorSettings(BaseSettings):
    ema_fast: int = 20
    ema_slow: int = 40
    sma_mid_fast: int = 50
    sma_mid_slow: int = 100
    sma_long_fast: int = 100
    sma_long_slow: int = 200
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_period: int = 14
    adx_period: int = 14


class StrategySettings(BaseSettings):
    rsi_long_min: float = 40.0
    rsi_long_max: float = 70.0
    rsi_short_min: float = 30.0
    rsi_short_max: float = 60.0
    reversal_lookback_bars: int = 5
    adx_consolidation_max: float = 20.0
    enabled_setups: list[str] = Field(
        default_factory=lambda: [
            "UptrendPullbackLong",
            "DowntrendBounceShort",
            "BullishReversalLong",
            "BearishReversalShort",
            "ConsolidationBreakout",
        ]
    )


class RiskSettings(BaseSettings):
    per_position_pct: float = 0.03
    max_total_exposure_pct: float = 0.20
    atr_stop_multiple: float = 1.0
    atr_target_multiple: float = 2.0
    trailing_atr_multiple: float = 1.0
    max_holding_days: int = 10


class SchedulerSettings(BaseSettings):
    scan_time_et: str = "16:30"
    order_time_et: str = "09:15"
    eod_review_time_et: str = "16:05"


class CacheSettings(BaseSettings):
    db_path: Path = Path(__file__).parent.parent / "data" / "ibkr.db"
    history_years: int = 3
    hist_request_delay_sec: float = 2.0


class Settings(BaseSettings):
    connection: ConnectionSettings = Field(default_factory=ConnectionSettings)
    universe: UniverseSettings = Field(default_factory=UniverseSettings)
    indicators: IndicatorSettings = Field(default_factory=IndicatorSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)


def load_settings() -> Settings:
    return Settings()
