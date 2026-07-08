"""
TCP v2 benchmark acquisition — committed v1 SPXTR methodology with safe failure modes.

Side-effect free on import: no network, no Dash/Flask, no ledger/JSON state I/O.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, Union

import pandas as pd

logger = logging.getLogger(__name__)

BENCHMARK_DUPLICATE_DATE_POLICY = "keep_first"

SPXTR_DISPLAY_NAME = "SPXTR"
SPXTR_SYMBOL = "^SP500TR"
SPXTR_INCEPTION_COLUMN = "SPXTR (Inception)"

BTC_DISPLAY_NAME = "BTC"
BTC_SYMBOL = "BTC-USD"

ETH_DISPLAY_NAME = "ETH"
ETH_SYMBOL = "ETH-USD"

DEFAULT_NETWORK_TIMEOUT_SECONDS = 10.0
DEFAULT_CACHE_FILENAME = "tcp_benchmark_cache.json"
DEFAULT_BTC_CACHE_FILENAME = "tcp_benchmark_btc_cache.json"
DEFAULT_ETH_CACHE_FILENAME = "tcp_benchmark_eth_cache.json"

BENCHMARK_STATUS_READY = "ready"
BENCHMARK_STATUS_STALE = "stale"
BENCHMARK_STATUS_UNAVAILABLE = "unavailable"


class BenchmarkNormalizationError(ValueError):
    """Controlled error for ambiguous or unsupported provider payloads."""


class BenchmarkProvider(Protocol):
  """Injectable benchmark return-series provider for tests."""

  def download_returns(self, symbol: str) -> pd.Series:
    ...


@dataclass(frozen=True)
class BenchmarkResult:
    """Structured benchmark payload for dashboard rendering."""

    status: str
    symbol: str
    display_name: str
    as_of: Optional[str]
    fetched_at: Optional[str]
    returns: Optional[pd.Series]
    warning: Optional[str]
    source: str = "quantstats"

    def to_store_dict(self) -> Dict[str, Any]:
        returns_payload: Optional[List[Dict[str, float]]] = None
        if self.returns is not None and not self.returns.empty:
            returns_payload = [
                {"date": idx.strftime("%Y-%m-%d"), "value": float(val)}
                for idx, val in self.returns.items()
                if pd.notna(val)
            ]
        return {
            "status": self.status,
            "symbol": self.symbol,
            "display_name": self.display_name,
            "as_of": self.as_of,
            "fetched_at": self.fetched_at,
            "warning": self.warning,
            "source": self.source,
            "returns": returns_payload,
        }

    @classmethod
    def from_store_dict(cls, payload: Mapping[str, Any]) -> "BenchmarkResult":
        returns = None
        raw = payload.get("returns")
        if raw:
            dates = [row["date"] for row in raw]
            values = [row["value"] for row in raw]
            returns = pd.Series(values, index=pd.to_datetime(dates), dtype=float)
        return cls(
            status=str(payload.get("status") or BENCHMARK_STATUS_UNAVAILABLE),
            symbol=str(payload.get("symbol") or SPXTR_SYMBOL),
            display_name=str(payload.get("display_name") or SPXTR_DISPLAY_NAME),
            as_of=payload.get("as_of"),
            fetched_at=payload.get("fetched_at"),
            returns=returns,
            warning=payload.get("warning"),
            source=str(payload.get("source") or "quantstats"),
        )

    def with_status(self, status: str, warning: Optional[str] = None) -> "BenchmarkResult":
        return BenchmarkResult(
            status=status,
            symbol=self.symbol,
            display_name=self.display_name,
            as_of=self.as_of,
            fetched_at=self.fetched_at,
            returns=self.returns,
            warning=warning if warning is not None else self.warning,
            source=self.source,
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _series_as_of(series: pd.Series) -> Optional[str]:
    if series is None or series.empty:
        return None
    return pd.Timestamp(series.index.max()).strftime("%Y-%m-%d")


def _symbol_match_variants(symbol: str) -> Tuple[str, ...]:
    base = symbol.lstrip("^")
    return tuple(dict.fromkeys((symbol, base, f"^{base}")))


def _pick_numeric_column(frame: pd.DataFrame, symbol: str) -> pd.Series:
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    preferred_fields = ("Adj Close", "Close", "close", "Return", "returns")
    symbol_variants = _symbol_match_variants(symbol)

    if isinstance(frame.columns, pd.MultiIndex):
        for field in preferred_fields:
            for sym in symbol_variants:
                for key in ((field, sym), (sym, field)):
                    if key in frame.columns:
                        return pd.to_numeric(frame[key], errors="coerce")
        matching = [
            col
            for col in frame.columns
            if any(part in symbol_variants for part in (col if isinstance(col, tuple) else (col,)))
        ]
        if len(matching) == 1:
            return pd.to_numeric(frame[matching[0]], errors="coerce")
        raise BenchmarkNormalizationError(
            f"Ambiguous MultiIndex benchmark columns for {symbol}: {list(frame.columns)}"
        )

    for field in preferred_fields:
        if field in numeric.columns and numeric[field].notna().any():
            return numeric[field]

    usable = [col for col in numeric.columns if numeric[col].notna().any()]
    if len(usable) == 1:
        return numeric[usable[0]]
    if not usable:
        return pd.Series(dtype=float)
    raise BenchmarkNormalizationError(
        f"Ambiguous benchmark DataFrame columns for {symbol}: {list(frame.columns)}"
    )


def normalize_provider_returns(
    data: Union[pd.Series, pd.DataFrame],
    symbol: str,
) -> pd.Series:
    """
    Normalize provider output to a finite daily return Series.

    Policy (committed v1 compatible):
    - Accept Series directly
    - Reduce one-column DataFrame deterministically
    - Select exact symbol/field from yfinance MultiIndex when unambiguous
    - Reject ambiguous multi-column payloads
    - ``pd.to_numeric(errors='coerce')``, drop inf/NaN
    - Sort dates ascending; duplicate dates keep first
    """
    if isinstance(data, pd.Series):
        series = pd.to_numeric(data, errors="coerce")
    elif isinstance(data, pd.DataFrame):
        if data.empty:
            return pd.Series(dtype=float)
        if data.shape[1] == 1:
            series = pd.to_numeric(data.iloc[:, 0], errors="coerce")
        else:
            series = _pick_numeric_column(data, symbol)
    else:
        raise BenchmarkNormalizationError(f"Unsupported provider payload type: {type(data)!r}")

    series = pd.Series(series.values, index=pd.to_datetime(series.index), dtype=float)
    series = series.sort_index()
    series = series.mask(series.abs() == float("inf"))
    series = series.dropna()
    if series.index.has_duplicates:
        if BENCHMARK_DUPLICATE_DATE_POLICY == "keep_first":
            series = series[~series.index.duplicated(keep="first")]
        else:
            raise BenchmarkNormalizationError(f"Duplicate benchmark dates for {symbol}")
    return series.astype(float)


def _validate_returns_series(series: pd.Series, symbol: str) -> pd.Series:
    if series is None or series.empty:
        raise ValueError(f"No returns returned for {symbol}")
    if not series.index.is_monotonic_increasing:
        series = series.sort_index()
    return series.astype(float)


class QuantstatsBenchmarkProvider:
    """Committed v1 provider: quantstats ``utils.download_returns``."""

    def download_returns(self, symbol: str) -> pd.Series:
        from quantstats import utils

        raw = utils.download_returns(symbol)
        series = normalize_provider_returns(raw, symbol)
        return _validate_returns_series(series, symbol)


def align_benchmark_returns(
    full_returns: pd.Series,
    nav_index: pd.DatetimeIndex,
) -> pd.Series:
    """Replicate v1 alignment: reindex to NAV dates, forward/back fill, dropna."""
    if full_returns is None or full_returns.empty or len(nav_index) == 0:
        return pd.Series(dtype=float)
    aligned = full_returns.reindex(nav_index).ffill().bfill().dropna()
    return aligned.astype(float)


def build_scaled_benchmark_nav(
    aligned_returns: pd.Series,
    *,
    inception_start: pd.Timestamp,
    baseline: float,
) -> pd.Series:
    """SPXTR NAV scaled to strategy baseline (committed v1)."""
    if aligned_returns.empty or baseline == 0:
        return pd.Series(dtype=float)
    sliced = aligned_returns.loc[inception_start:].astype(float)
    if sliced.empty:
        return pd.Series(dtype=float)
    return (1.0 + sliced).cumprod() * float(baseline)


def _serialize_returns(series: pd.Series) -> List[Dict[str, float]]:
    return [
        {"date": idx.strftime("%Y-%m-%d"), "value": float(val)}
        for idx, val in series.items()
        if pd.notna(val)
    ]


def _deserialize_returns(rows: Sequence[Mapping[str, Any]]) -> pd.Series:
    dates = [row["date"] for row in rows]
    values = [row["value"] for row in rows]
    series = pd.Series(values, index=pd.to_datetime(dates), dtype=float)
    return series.sort_index()


def _read_cache(cache_path: Path, *, expected_symbol: str) -> Optional[Dict[str, Any]]:
    if not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Ignoring corrupt benchmark cache: %s", exc)
        return None
    if not isinstance(payload, dict):
        return None
    if not payload.get("returns"):
        return None
    cached_symbol = str(payload.get("symbol") or "")
    if cached_symbol and cached_symbol not in _symbol_match_variants(expected_symbol):
        logger.warning("Ignoring benchmark cache with unexpected symbol %s", cached_symbol)
        return None
    try:
        series = _deserialize_returns(payload["returns"])
        _validate_returns_series(series, expected_symbol)
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Ignoring invalid benchmark cache payload: %s", exc)
        return None
    return payload


def _write_cache_atomic(cache_path: Path, payload: Dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, cache_path)


def _fetch_returns_with_timeout(
    provider: BenchmarkProvider,
    symbol: str,
    timeout_seconds: float,
) -> pd.Series:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(provider.download_returns, symbol)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            raise TimeoutError(f"Benchmark download timed out after {timeout_seconds}s") from exc


def load_symbol_benchmark_cache_only(
    *,
    symbol: str,
    display_name: str,
    cache_path: Optional[Path] = None,
    default_cache_filename: str = DEFAULT_CACHE_FILENAME,
) -> BenchmarkResult:
    """Serve validated on-disk benchmark cache without a network fetch."""
    cache_path = cache_path or Path("_runtime") / default_cache_filename
    cached = _read_cache(cache_path, expected_symbol=symbol)
    if not cached:
        return BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=symbol,
            display_name=display_name,
            as_of=None,
            fetched_at=None,
            returns=None,
            warning=f"{display_name} benchmark data is temporarily unavailable.",
        )
    series = _deserialize_returns(cached["returns"])
    return BenchmarkResult(
        status=BENCHMARK_STATUS_READY,
        symbol=symbol,
        display_name=display_name,
        as_of=cached.get("as_of") or _series_as_of(series),
        fetched_at=cached.get("fetched_at"),
        returns=series,
        warning=None,
        source=str(cached.get("source") or "quantstats"),
    )


def load_symbol_benchmark(
    *,
    symbol: str,
    display_name: str,
    provider: Optional[BenchmarkProvider] = None,
    cache_path: Optional[Path] = None,
    default_cache_filename: str = DEFAULT_CACHE_FILENAME,
    timeout_seconds: float = DEFAULT_NETWORK_TIMEOUT_SECONDS,
    now: Optional[Callable[[], datetime]] = None,
) -> BenchmarkResult:
    """
    Live bounded fetch with last-known-good disk cache (strategy A).

    - ``ready``: fresh network fetch succeeded
    - ``stale``: network failed; valid cache served with explicit warning
    - ``unavailable``: no network data and no valid cache
    """
    provider = provider or QuantstatsBenchmarkProvider()
    cache_path = cache_path or Path("_runtime") / default_cache_filename

    cached = _read_cache(cache_path, expected_symbol=symbol)
    cached_series: Optional[pd.Series] = None
    if cached and cached.get("returns"):
        try:
            cached_series = _deserialize_returns(cached["returns"])
        except (KeyError, TypeError, ValueError):
            cached_series = None

    try:
        raw = _fetch_returns_with_timeout(provider, symbol, timeout_seconds)
        series = normalize_provider_returns(raw, symbol)
        series = _validate_returns_series(series, symbol)
        snapshot = deepcopy(series)
        fetched_at = _utc_now_iso()
        as_of = _series_as_of(snapshot)
        _write_cache_atomic(
            cache_path,
            {
                "symbol": symbol,
                "display_name": display_name,
                "fetched_at": fetched_at,
                "as_of": as_of,
                "source": "quantstats",
                "returns": _serialize_returns(snapshot),
            },
        )
        return BenchmarkResult(
            status=BENCHMARK_STATUS_READY,
            symbol=symbol,
            display_name=display_name,
            as_of=as_of,
            fetched_at=fetched_at,
            returns=snapshot,
            warning=None,
        )
    except Exception as exc:
        logger.warning("%s benchmark fetch failed: %s", display_name, exc)
        if cached_series is not None and not cached_series.empty:
            return BenchmarkResult(
                status=BENCHMARK_STATUS_STALE,
                symbol=symbol,
                display_name=display_name,
                as_of=cached.get("as_of") or _series_as_of(cached_series),
                fetched_at=cached.get("fetched_at"),
                returns=cached_series,
                warning="Benchmark data is stale; showing last successful download.",
                source=str(cached.get("source") or "quantstats"),
            )
        return BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=symbol,
            display_name=display_name,
            as_of=None,
            fetched_at=None,
            returns=None,
            warning=f"{display_name} benchmark data is temporarily unavailable.",
        )


def load_spxtr_benchmark_cache_only(
    *,
    cache_path: Optional[Path] = None,
) -> BenchmarkResult:
    return load_symbol_benchmark_cache_only(
        symbol=SPXTR_SYMBOL,
        display_name=SPXTR_DISPLAY_NAME,
        cache_path=cache_path,
        default_cache_filename=DEFAULT_CACHE_FILENAME,
    )


def load_spxtr_benchmark(
    *,
    provider: Optional[BenchmarkProvider] = None,
    cache_path: Optional[Path] = None,
    timeout_seconds: float = DEFAULT_NETWORK_TIMEOUT_SECONDS,
    now: Optional[Callable[[], datetime]] = None,
) -> BenchmarkResult:
    return load_symbol_benchmark(
        symbol=SPXTR_SYMBOL,
        display_name=SPXTR_DISPLAY_NAME,
        provider=provider,
        cache_path=cache_path,
        default_cache_filename=DEFAULT_CACHE_FILENAME,
        timeout_seconds=timeout_seconds,
        now=now,
    )


def load_btc_benchmark(
    *,
    provider: Optional[BenchmarkProvider] = None,
    cache_path: Optional[Path] = None,
    timeout_seconds: float = DEFAULT_NETWORK_TIMEOUT_SECONDS,
    now: Optional[Callable[[], datetime]] = None,
) -> BenchmarkResult:
    return load_symbol_benchmark(
        symbol=BTC_SYMBOL,
        display_name=BTC_DISPLAY_NAME,
        provider=provider,
        cache_path=cache_path,
        default_cache_filename=DEFAULT_BTC_CACHE_FILENAME,
        timeout_seconds=timeout_seconds,
        now=now,
    )


def load_btc_benchmark_cache_only(
    *,
    cache_path: Optional[Path] = None,
) -> BenchmarkResult:
    return load_symbol_benchmark_cache_only(
        symbol=BTC_SYMBOL,
        display_name=BTC_DISPLAY_NAME,
        cache_path=cache_path,
        default_cache_filename=DEFAULT_BTC_CACHE_FILENAME,
    )


def load_eth_benchmark(
    *,
    provider: Optional[BenchmarkProvider] = None,
    cache_path: Optional[Path] = None,
    timeout_seconds: float = DEFAULT_NETWORK_TIMEOUT_SECONDS,
    now: Optional[Callable[[], datetime]] = None,
) -> BenchmarkResult:
    return load_symbol_benchmark(
        symbol=ETH_SYMBOL,
        display_name=ETH_DISPLAY_NAME,
        provider=provider,
        cache_path=cache_path,
        default_cache_filename=DEFAULT_ETH_CACHE_FILENAME,
        timeout_seconds=timeout_seconds,
        now=now,
    )


def load_eth_benchmark_cache_only(
    *,
    cache_path: Optional[Path] = None,
) -> BenchmarkResult:
    return load_symbol_benchmark_cache_only(
        symbol=ETH_SYMBOL,
        display_name=ETH_DISPLAY_NAME,
        cache_path=cache_path,
        default_cache_filename=DEFAULT_ETH_CACHE_FILENAME,
    )


def benchmark_status_message(result: BenchmarkResult) -> Optional[str]:
    if result.status == BENCHMARK_STATUS_READY:
        if result.as_of:
            return f"SPXTR source: {result.source}. Data as of {result.as_of}."
        return f"SPXTR source: {result.source}."
    if result.status == BENCHMARK_STATUS_STALE:
        as_of = result.as_of or "unknown date"
        return f"SPXTR benchmark data is stale (last successful as-of {as_of})."
    if result.status == BENCHMARK_STATUS_UNAVAILABLE:
        return result.warning or "SPXTR benchmark data is temporarily unavailable."
    return None
