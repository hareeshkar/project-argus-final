from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if hasattr(value, "item"):
            value = value.item()
        if pd.isna(value) or not np.isfinite(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if hasattr(value, "item"):
            value = value.item()
        if pd.isna(value) or not np.isfinite(value):
            return default
        return int(value)
    except Exception:
        return default


@dataclass(frozen=True)
class AnalyticsConfig:
    arima_orders: Tuple[Tuple[int, int, int], ...] = (
        (0, 1, 0),
        (1, 1, 0),
        (0, 1, 1),
        (1, 1, 1),
        (2, 1, 1),
        (2, 1, 2),
    )
    ewma_lambda: float = 0.94
    anomaly_lookback: int = 20


class AnalyticsEngine:
    """Statistically honest analytics for CSE's short public data window."""

    def __init__(self, config: Optional[AnalyticsConfig] = None):
        self.config = config or AnalyticsConfig()

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        frame = self._prepare(df)
        arima = self._run_arima(frame)
        volatility = self._run_volatility(frame)
        anomaly = self._run_anomaly(frame)
        drawdown = self._run_drawdown(frame)
        trend = self._run_trend(frame)
        regime = self._run_regime(frame, volatility, trend)
        confidence = self._run_confidence(frame, arima, volatility, anomaly, regime)
        indicator_vote = self._run_indicator_vote(arima, trend, volatility, anomaly, regime, confidence)

        return {
            "arima": arima,
            "volatility": volatility,
            "anomaly": anomaly,
            "zscore": anomaly,
            "drawdown": drawdown,
            "trend": trend,
            "linreg": trend,
            "regime": regime,
            "confidence": confidence,
            "indicator_vote": indicator_vote,
            "data_points": len(frame),
            "analysis_timestamp": pd.Timestamp.utcnow().isoformat(),
            "overall_health": "HEALTHY",
        }

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        required = {"close", "high", "low", "volume"}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"Missing required OHLCV columns: {sorted(missing)}")

        frame = df.copy()
        if "timestamp" in frame.columns:
            frame = frame.sort_values("timestamp")

        for column in ["open", "high", "low", "close", "volume"]:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

        frame = frame.dropna(subset=["close", "high", "low", "volume"]).reset_index(drop=True)
        frame = frame[frame["close"] > 0]
        return frame

    def _log_prices(self, frame: pd.DataFrame) -> pd.Series:
        close = frame["close"].dropna()
        close = close[close > 0]
        return np.log(close)

    def _log_returns(self, frame: pd.DataFrame) -> pd.Series:
        log_prices = self._log_prices(frame)
        return log_prices.diff().dropna()

    def _aicc(self, aic: float, n_obs: int, parameter_count: int) -> float:
        if n_obs <= parameter_count + 1:
            return safe_float(aic)
        return safe_float(aic + (2 * parameter_count * (parameter_count + 1)) / (n_obs - parameter_count - 1))

    def _run_arima(self, frame: pd.DataFrame) -> Dict[str, Any]:
        log_prices = self._log_prices(frame)
        result = {
            "model_used": "fallback",
            "candidate_models": [f"ARIMA{order}" for order in self.config.arima_orders],
            "selected_order": [0, 1, 0],
            "aic": 0.0,
            "aicc": 0.0,
            "bic": 0.0,
            "forecast": [safe_float(frame["close"].iloc[-1])] * 3,
            "confidence_interval": {
                "lower": [safe_float(frame["close"].iloc[-1])] * 3,
                "upper": [safe_float(frame["close"].iloc[-1])] * 3,
            },
            "trend": "FLAT",
            "beats_naive": False,
            "forecast_confidence": "LOW",
            "residual_white_noise_pvalue": 0.0,
            "error": None,
        }

        if len(log_prices) < 20:
            result["error"] = "Insufficient observations for ARIMA"
            return result

        best_fit = None
        best_order = None
        best_aicc = float("inf")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for order in self.config.arima_orders:
                try:
                    fit = ARIMA(log_prices, order=order).fit()
                    parameter_count = max(1, sum(order))
                    fit_aicc = self._aicc(fit.aic, len(log_prices), parameter_count)
                    if fit_aicc < best_aicc:
                        best_fit = fit
                        best_order = order
                        best_aicc = fit_aicc
                except Exception:
                    continue

        if best_fit is None or best_order is None:
            result["error"] = "All bounded ARIMA candidates failed"
            return result

        forecast_frame = best_fit.get_forecast(steps=3).summary_frame(alpha=0.05)
        forecast = np.exp(forecast_frame["mean"])
        lower = np.exp(forecast_frame["mean_ci_lower"])
        upper = np.exp(forecast_frame["mean_ci_upper"])

        try:
            naive_fit = ARIMA(log_prices, order=(0, 1, 0)).fit()
            model_rmse = np.sqrt(np.nanmean(np.square(best_fit.resid.dropna())))
            naive_rmse = np.sqrt(np.nanmean(np.square(naive_fit.resid.dropna())))
            beats_naive = bool(model_rmse < naive_rmse)
        except Exception:
            beats_naive = False

        lb_pvalue = 0.0
        try:
            resid = best_fit.resid.dropna()
            if len(resid) > 10:
                lb_test = acorr_ljungbox(resid, lags=[10], return_df=True)
                lb_pvalue = safe_float(lb_test["lb_pvalue"].iloc[0])
        except Exception:
            lb_pvalue = 0.0

        first = safe_float(forecast.iloc[0])
        last = safe_float(forecast.iloc[-1])
        trend = "UP" if last > first * 1.01 else ("DOWN" if last < first * 0.99 else "FLAT")

        result.update(
            {
                "model_used": f"ARIMA{best_order}",
                "selected_order": list(best_order),
                "aic": safe_float(best_fit.aic),
                "aicc": safe_float(best_aicc),
                "bic": safe_float(best_fit.bic),
                "forecast": [safe_float(value) for value in forecast],
                "confidence_interval": {
                    "lower": [safe_float(value) for value in lower],
                    "upper": [safe_float(value) for value in upper],
                },
                "trend": trend,
                "beats_naive": beats_naive,
                "forecast_confidence": "MODERATE" if beats_naive and lb_pvalue > 0.05 else "LOW",
                "residual_white_noise_pvalue": lb_pvalue,
            }
        )
        return result

    def _run_volatility(self, frame: pd.DataFrame) -> Dict[str, Any]:
        returns = self._log_returns(frame)
        if len(returns) < 5:
            return {"error": "Insufficient return observations"}

        variance = returns.var()
        for value in returns:
            variance = self.config.ewma_lambda * variance + (1 - self.config.ewma_lambda) * value**2

        ewma_vol = np.sqrt(variance)
        daily_vol_pct = ewma_vol * 100
        parametric_var_95 = (-returns.mean() + 1.645 * ewma_vol) * 100
        historical_var_95 = abs(np.percentile(returns, 5)) * 100
        historical_var_99 = abs(np.percentile(returns, 1)) * 100

        high = frame["high"]
        low = frame["low"]
        valid = (high > 0) & (low > 0) & (high >= low)
        log_hl = np.log(high[valid] / low[valid])
        parkinson = np.sqrt(((log_hl**2).mean()) / (4 * np.log(2))) * 100 if len(log_hl) else 0.0
        flat_high_low_ratio = safe_float((high[valid] == low[valid]).mean()) if len(log_hl) else 0.0

        rolling_vol = returns.rolling(20).std().dropna() * 100
        volatility_percentile = stats.percentileofscore(rolling_vol, daily_vol_pct) if len(rolling_vol) else 0.0

        risk_level = "LOW" if daily_vol_pct < 1 else ("MODERATE" if daily_vol_pct < 2.5 else "HIGH")

        return {
            "daily_volatility_pct": safe_float(daily_vol_pct),
            "ewma_lambda": self.config.ewma_lambda,
            "var_95_pct": safe_float(parametric_var_95),
            "historical_var_95_pct": safe_float(historical_var_95),
            "historical_var_99_pct": safe_float(historical_var_99),
            "parkinson_volatility_pct": safe_float(parkinson),
            "flat_high_low_ratio": flat_high_low_ratio,
            "volatility_percentile": safe_float(volatility_percentile),
            "risk_level": risk_level,
            "error": None,
        }

    def _modified_zscore(self, values: pd.Series) -> float:
        clean = values.dropna()
        if len(clean) < 5:
            return 0.0
        median = clean.median()
        mad = stats.median_abs_deviation(clean, scale="normal")
        if mad == 0 or pd.isna(mad):
            return 0.0
        return safe_float((clean.iloc[-1] - median) / mad)

    def _classical_zscore(self, values: pd.Series) -> float:
        clean = values.dropna()
        std = clean.std()
        if len(clean) < 5 or std == 0 or pd.isna(std):
            return 0.0
        return safe_float((clean.iloc[-1] - clean.mean()) / std)

    def _run_anomaly(self, frame: pd.DataFrame) -> Dict[str, Any]:
        returns = self._log_returns(frame).tail(self.config.anomaly_lookback)
        volume = frame["volume"].replace(0, np.nan).dropna()
        volume_changes = np.log(volume / volume.shift(1)).dropna().tail(self.config.anomaly_lookback)

        return_z = self._classical_zscore(returns)
        volume_z = self._classical_zscore(volume_changes)
        modified_return_z = self._modified_zscore(returns)
        modified_volume_z = self._modified_zscore(volume_changes)
        return_anomaly = abs(modified_return_z) > 3.5
        volume_anomaly = abs(modified_volume_z) > 3.5

        return {
            "return_zscore": return_z,
            "volume_zscore": volume_z,
            "price_zscore": return_z,
            "modified_return_zscore": modified_return_z,
            "modified_price_zscore": modified_return_z,
            "modified_volume_zscore": modified_volume_z,
            "return_anomaly": return_anomaly,
            "price_anomaly": return_anomaly,
            "volume_anomaly": volume_anomaly,
            "is_anomalous": bool(return_anomaly or volume_anomaly),
            "lookback_days": self.config.anomaly_lookback,
            "error": None,
        }

    def _run_drawdown(self, frame: pd.DataFrame) -> Dict[str, Any]:
        close = frame["close"]
        peak = close.cummax()
        drawdowns = (close / peak - 1) * 100
        duration = 0
        for value in reversed(drawdowns.tolist()):
            if value < 0:
                duration += 1
            else:
                break
        return {
            "current_drawdown_pct": safe_float(drawdowns.iloc[-1]),
            "max_drawdown_pct": safe_float(drawdowns.min()),
            "drawdown_duration_days": safe_int(duration),
            "error": None,
        }

    def _run_trend(self, frame: pd.DataFrame) -> Dict[str, Any]:
        prices = np.log(frame["close"].tail(30))
        if len(prices) < 5:
            return {"error": "Insufficient trend observations"}
        x = np.arange(1, len(prices) + 1)
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, prices)
        direction = "UP" if slope > 0.0001 else ("DOWN" if slope < -0.0001 else "FLAT")
        return {
            "slope": safe_float(slope),
            "r_squared": safe_float(r_value**2),
            "p_value": safe_float(p_value),
            "std_error": safe_float(std_err),
            "trend_direction": direction,
            "is_strong_trend": bool(abs(slope) > 0.0001 and (r_value**2) > 0.3),
            "days_analyzed": len(prices),
            "error": None,
        }

    def _run_regime(self, frame: pd.DataFrame, volatility: Dict[str, Any], trend: Dict[str, Any]) -> Dict[str, Any]:
        volume = frame["volume"].dropna()
        volume_percentile = stats.percentileofscore(volume, volume.iloc[-1]) if len(volume) else 0.0
        volatility_percentile = safe_float(volatility.get("volatility_percentile", 0.0))

        return {
            "trend_regime": trend.get("trend_direction", "FLAT") if trend.get("trend_direction") != "FLAT" else "SIDEWAYS",
            "volatility_regime": "HIGH" if volatility_percentile >= 80 else ("LOW" if volatility_percentile <= 20 else "NORMAL"),
            "liquidity_regime": "THIN" if volume_percentile <= 20 else "LIQUID",
            "volume_percentile": safe_float(volume_percentile),
            "volatility_percentile": volatility_percentile,
        }

    def _run_confidence(
        self,
        frame: pd.DataFrame,
        arima: Dict[str, Any],
        volatility: Dict[str, Any],
        anomaly: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> Dict[str, Any]:
        penalties = {
            "insufficient_rows": 0.0 if len(frame) >= 120 else 0.2,
            "model_underperformance": 0.0 if arima.get("beats_naive") else 0.15,
            "arima_diagnostics": 0.0 if arima.get("residual_white_noise_pvalue", 0.0) > 0.05 else 0.1,
            "missing_values": safe_float(min(frame.isna().mean().mean(), 0.3)),
            "thin_liquidity": 0.1 if regime.get("liquidity_regime") == "THIN" else 0.0,
            "flat_high_low": 0.1 if volatility.get("flat_high_low_ratio", 0.0) >= 0.2 else 0.0,
        }
        score = max(0.0, min(1.0, 1.0 - sum(penalties.values())))
        label = "HIGH" if score >= 0.75 else ("MODERATE" if score >= 0.5 else "LOW")

        reasons: List[str] = []
        if penalties["insufficient_rows"] == 0:
            reasons.append("Sufficient daily data available within CSE API cap")
        if penalties["model_underperformance"]:
            reasons.append("ARIMA did not outperform random-walk baseline proxy")
        if anomaly.get("is_anomalous"):
            reasons.append("Robust anomaly flag is active")
        if penalties["thin_liquidity"]:
            reasons.append("Latest volume is in the lower historical percentile for this symbol")

        return {
            "score": safe_float(score),
            "label": label,
            "penalties": penalties,
            "reasons": reasons,
        }

    def _run_indicator_vote(
        self,
        arima: Dict[str, Any],
        trend: Dict[str, Any],
        volatility: Dict[str, Any],
        anomaly: Dict[str, Any],
        regime: Dict[str, Any],
        confidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        trend_score = 0.0
        if arima.get("trend") == "UP":
            trend_score += 0.2
        elif arima.get("trend") == "DOWN":
            trend_score -= 0.2
        if trend.get("trend_direction") == "UP":
            trend_score += 0.2
        elif trend.get("trend_direction") == "DOWN":
            trend_score -= 0.2

        volatility_score = -0.15 if volatility.get("risk_level") == "HIGH" else 0.05
        liquidity_score = -0.1 if regime.get("liquidity_regime") == "THIN" else 0.1
        anomaly_score = -0.15 if anomaly.get("is_anomalous") else 0.0
        raw_score = trend_score + volatility_score + liquidity_score + anomaly_score
        score = max(-1.0, min(1.0, raw_score * confidence.get("score", 0.5)))
        signal = "BULLISH" if score >= 0.2 else ("BEARISH" if score <= -0.2 else "NEUTRAL")

        return {
            "signal": signal,
            "score": safe_float(score),
            "confidence": safe_float(confidence.get("score", 0.0)),
            "drivers": confidence.get("reasons", []),
            "components": {
                "trend_score": safe_float(trend_score),
                "volatility_score": safe_float(volatility_score),
                "liquidity_score": safe_float(liquidity_score),
                "anomaly_score": safe_float(anomaly_score),
            },
        }
