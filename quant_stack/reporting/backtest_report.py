"""Standard backtest report generation with Plotly charts and pipeline gate."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import BaseModel, Field


class ReportPolicy(str, Enum):
    PASS_ONLY = "pass_only"
    ALWAYS = "always"
    NEVER = "never"


class GateConfig(BaseModel):
    min_trades: int = 30
    max_drawdown_pct: float = 0.25
    min_profit_factor: float = 1.0
    min_sharpe: float = 0.0
    min_cumulative_return: float = 0.0
    require_backtest_result: bool = True
    report_policy: ReportPolicy = ReportPolicy.PASS_ONLY


class PipelineGateResult(BaseModel):
    passed: bool
    stage: str = "initial"
    reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "passed": self.passed,
            "stage": self.stage,
            "reasons": self.reasons,
            "metrics": self.metrics,
            "warnings": self.warnings,
        }


def run_pipeline_gate(
    metrics: dict[str, Any],
    trades_count: int = 0,
    config: GateConfig | None = None,
) -> PipelineGateResult:
    """Run pipeline gate validation on backtest results.
    
    Args:
        metrics: Backtest metrics dictionary
        trades_count: Number of trades in the backtest
        config: Gate configuration (defaults to GateConfig)
        
    Returns:
        PipelineGateResult with pass/fail status and reasons
    """
    if config is None:
        config = GateConfig()
    
    reasons: list[str] = []
    warnings: list[str] = []
    
    cumulative_return = metrics.get("cumulative_return", 0)
    max_drawdown = abs(metrics.get("max_drawdown", 0))
    sharpe = metrics.get("smart_sharpe", 0)
    
    gross_profit = metrics.get("gross_profit", 0)
    gross_loss = abs(metrics.get("gross_loss", 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    
    if config.require_backtest_result and not metrics:
        return PipelineGateResult(
            passed=False,
            stage="backtest_result",
            reasons=["No backtest result metrics provided"],
        )
    
    if trades_count < config.min_trades:
        reasons.append(f"trade_count ({trades_count}) below minimum ({config.min_trades})")
    
    if max_drawdown > config.max_drawdown_pct:
        reasons.append(f"max_drawdown ({max_drawdown:.2%}) exceeds threshold ({config.max_drawdown_pct:.2%})")
    
    if profit_factor < config.min_profit_factor:
        reasons.append(f"profit_factor ({profit_factor:.2f}) below minimum ({config.min_profit_factor:.2f})")
    
    if sharpe < config.min_sharpe:
        reasons.append(f"sharpe ({sharpe:.3f}) below minimum ({config.min_sharpe:.3f})")
    
    if cumulative_return < config.min_cumulative_return:
        reasons.append(f"cumulative_return ({cumulative_return:.4f}) below minimum ({config.min_cumulative_return:.4f})")
    
    if trades_count > 0 and trades_count < 50:
        warnings.append(f"Low trade count ({trades_count}) - results may not be statistically significant")
    
    passed = len(reasons) == 0
    
    return PipelineGateResult(
        passed=passed,
        stage="gate_validation",
        reasons=reasons,
        warnings=warnings,
        metrics={
            "trade_count": trades_count,
            "cumulative_return": cumulative_return,
            "max_drawdown": max_drawdown,
            "profit_factor": profit_factor,
            "sharpe": sharpe,
            "cagr": metrics.get("cagr"),
            "time_in_market": metrics.get("time_in_market"),
        },
    )


def write_backtest_artifacts(
    result_frame: pl.DataFrame,
    metrics: dict[str, Any],
    run_config: dict,
    output_dir: Path,
    title: str | None = None,
    gate_config: GateConfig | None = None,
) -> dict[str, Path]:
    """Write standard backtest artifacts to output directory.
    
    Args:
        result_frame: DataFrame with columns: timestamp, equity, position, is_exposed, etc.
        metrics: Dictionary of calculated metrics
        run_config: Configuration used for the backtest
        output_dir: Directory to write artifacts
        title: Optional title for the report
        gate_config: Gate configuration for pipeline validation
        
    Returns:
        Dictionary mapping artifact names to paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    artifacts = {}
    
    # summary.json
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    artifacts["summary.json"] = summary_path
    
    # run_config.json
    config_path = output_dir / "run_config.json"
    with open(config_path, "w") as f:
        json.dump(run_config, f, indent=2)
    artifacts["run_config.json"] = config_path
    
    # trades.parquet - extract trade records from frame
    trades_df = _extract_trades(result_frame)
    if trades_df is not None and not trades_df.is_empty():
        trades_path = output_dir / "trades.parquet"
        trades_df.write_parquet(trades_path)
        artifacts["trades.parquet"] = trades_path
    else:
        trades_df = None
    
    # Run pipeline gate
    if gate_config is None:
        gate_config = GateConfig()
    trade_count = len(trades_df) if trades_df is not None else 0
    gate_result = run_pipeline_gate(metrics, trade_count, gate_config)
    
    # Write gate_result.json
    gate_path = output_dir / "gate_result.json"
    with open(gate_path, "w") as f:
        json.dump(gate_result.to_json(), f, indent=2)
    artifacts["gate_result.json"] = gate_path
    
    # receipt.md
    receipt_path = output_dir / "receipt.md"
    initial_capital = run_config.get("initial_capital", 10000)
    final_equity = metrics.get("cumulative_return", 0) * initial_capital + initial_capital
    ret_pct = metrics.get("cumulative_return", 0) * 100
    dd_pct = metrics.get("max_drawdown", 0) * 100
    
    trade_count = len(trades_df) if trades_df is not None else 0
    win_count = 0
    if trades_df is not None and "pnl" in trades_df.columns:
        win_count = int(trades_df.filter(pl.col("pnl") > 0).height)
    win_rate_pct = win_count / trade_count * 100 if trade_count > 0 else 0
    
    receipt = f"""# Backtest Receipt

**Strategy:** {run_config.get('strategy', 'N/A')}
**Data:** {run_config.get('data_path', 'N/A')}
**Range:** {run_config.get('start', 'start')} to {run_config.get('end', 'end')}
**Rows used:** {run_config.get('rows_used', 'N/A')}

## Results
- **Initial capital:** ${initial_capital:,.2f}
- **Final equity:** ${final_equity:,.2f}
- **Cumulative return:** {ret_pct:.2f}%
- **Max drawdown:** {dd_pct:.2f}%
- **Sharpe (smart):** {metrics.get('smart_sharpe', 'N/A')}
- **CAGR:** {metrics.get('cagr', 'N/A')}
- **Time in market:** {metrics.get('time_in_market', 0)*100:.1f}%
- **Total trades:** {trade_count}
- **Win rate:** {win_rate_pct:.1f}%

**Artifact path:** {output_dir}
"""
    with open(receipt_path, "w") as f:
        f.write(receipt)
    artifacts["receipt.md"] = receipt_path
    
    # Determine if we should generate HTML report
    should_generate_report = _should_generate_html_report(gate_result, gate_config)
    
    if should_generate_report:
        ohlcv_frame = None
        if "open" in result_frame.columns and "high" in result_frame.columns:
            ohlcv_frame = result_frame
        
        html_path = render_backtest_report(
            result_frame=result_frame,
            metrics=metrics,
            run_config=run_config,
            output_path=output_dir / "report.html",
            title=title or f"{run_config.get('strategy', 'Backtest')} Results",
            trades=trades_df,
            ohlcv_frame=ohlcv_frame,
        )
        artifacts["report.html"] = html_path
    else:
        failure_path = _write_failure_report(gate_result, run_config, output_dir)
        artifacts["failure_report.md"] = failure_path
    
    return artifacts


def render_backtest_report(
    result_frame: pl.DataFrame,
    metrics: dict[str, Any],
    run_config: dict,
    output_path: Path,
    title: str,
    trades: pl.DataFrame | None = None,
    ohlcv_frame: pl.DataFrame | None = None,
) -> Path:
    """Render interactive HTML report with Plotly charts.
    
    Args:
        result_frame: DataFrame with backtest results (timestamp, equity, position, etc.)
        metrics: Calculated metrics dictionary
        run_config: Backtest configuration
        output_path: Path to write HTML report
        title: Report title
        trades: Optional trades DataFrame
        ohlcv_frame: Optional OHLCV DataFrame for price chart
        
    Returns:
        Path to created report
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    frame = result_frame.sort("timestamp")
    timestamps = frame["timestamp"].to_list()
    equity = frame["equity"].to_list()
    
    # Calculate drawdown
    peak = frame["equity"].cum_max().to_list()
    drawdown = [(e - p) / p * 100 for e, p in zip(equity, peak)]
    
    # Create figure with subplots
    fig = make_subplots(
        rows=3, cols=2,
        specs=[
            [{"colspan": 2, "rowspan": 1}, None],
            [{"colspan": 2, "rowspan": 1}, None],
            [{"colspan": 1, "rowspan": 1}, {"colspan": 1, "rowspan": 1}],
        ],
        subplot_titles=("Equity Curve", "Drawdown", "Price Chart", "Trade Distribution"),
        vertical_spacing=0.08,
        row_heights=[0.35, 0.35, 0.30],
    )
    
    # 1. Equity Curve
    fig.add_trace(
        go.Scatter(x=timestamps, y=equity, mode="lines", name="Equity", line=dict(color="#2E86AB")),
        row=1, col=1
    )
    
    # 2. Drawdown
    fig.add_trace(
        go.Scatter(x=timestamps, y=drawdown, mode="lines", name="Drawdown %", 
                   line=dict(color="#E94F37"), fill="tozeroy", fillcolor="rgba(233,79,55,0.2)"),
        row=2, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
    
    # 3. Price Chart (if OHLC available)
    if ohlcv_frame is not None and "open" in ohlcv_frame.columns:
        ohlcv = ohlcv_frame.sort("timestamp")
        fig.add_trace(
            go.Candlestick(
                x=ohlcv["timestamp"].to_list(),
                open=ohlcv["open"].to_list(),
                high=ohlcv["high"].to_list(),
                low=ohlcv["low"].to_list(),
                close=ohlcv["close"].to_list(),
                name="OHLC",
            ),
            row=3, col=1
        )
        
        # Add trade markers if trades exist
        if trades is not None and not trades.is_empty():
            buys = trades.filter(pl.col("side") == 1)
            sells = trades.filter(pl.col("side") == -1)
            
            if not buys.is_empty():
                fig.add_trace(
                    go.Scatter(
                        x=buys["entry_time"].to_list(),
                        y=buys["entry_price"].to_list(),
                        mode="markers",
                        marker=dict(symbol="triangle-up", size=10, color="green"),
                        name="Buy",
                    ),
                    row=3, col=1
                )
            if not sells.is_empty():
                fig.add_trace(
                    go.Scatter(
                        x=sells["entry_time"].to_list(),
                        y=sells["entry_price"].to_list(),
                        mode="markers",
                        marker=dict(symbol="triangle-down", size=10, color="red"),
                        name="Sell",
                    ),
                    row=3, col=1
                )
    else:
        # Fallback to close price
        if "close" in frame.columns:
            fig.add_trace(
                go.Scatter(x=timestamps, y=frame["close"].to_list(), mode="lines", name="Close", line=dict(color="#888")),
                row=3, col=1
            )
    
    # 4. Trade Distribution (histogram of PnL)
    if trades is not None and not trades.is_empty() and "pnl" in trades.columns:
        pnls = trades["pnl"].to_list()
        fig.add_trace(
            go.Histogram(x=pnls, name="P&L", marker_color="#2E86AB", nbinsx=30),
            row=3, col=2
        )
        fig.add_vline(x=0, line_dash="dash", line_color="red", row=3, col=2)
    
    # Calculate summary stats
    initial_capital = run_config.get("initial_capital", 10000)
    final_equity = equity[-1] if equity else initial_capital
    net_profit = final_equity - initial_capital
    total_return = (net_profit / initial_capital) * 100
    max_dd = min(drawdown) if drawdown else 0
    
    win_count = 0
    loss_count = 0
    if trades is not None and "pnl" in trades.columns:
        win_count = int(trades.filter(pl.col("pnl") > 0).height)
        loss_count = int(trades.filter(pl.col("pnl") < 0).height)
    total_trades = win_count + loss_count
    win_rate_pct = win_count / total_trades * 100 if total_trades > 0 else 0
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    
    # Calculate profit factor
    gross_profit = 0
    gross_loss = 0
    if trades is not None and "pnl" in trades.columns:
        gross_profit = float(trades.filter(pl.col("pnl") > 0).select(pl.col("pnl").sum()).item() or 0)
        gross_loss = abs(float(trades.filter(pl.col("pnl") < 0).select(pl.col("pnl").sum()).item() or 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    
    # Build HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #2E86AB; padding-bottom: 10px; }}
        .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin: 20px 0; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .card-value {{ font-size: 24px; font-weight: 600; color: #1a1a1a; }}
        .card-value.positive {{ color: #22c55e; }}
        .card-value.negative {{ color: #ef4444; }}
        .chart {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 15px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f8f8; font-weight: 600; }}
        .positive {{ color: #22c55e; }}
        .negative {{ color: #ef4444; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        
        <div class="dashboard">
            <div class="card">
                <div class="card-label">Initial Capital</div>
                <div class="card-value">${initial_capital:,.0f}</div>
            </div>
            <div class="card">
                <div class="card-label">Final Equity</div>
                <div class="card-value">${final_equity:,.2f}</div>
            </div>
            <div class="card">
                <div class="card-label">Net Profit</div>
                <div class="card-value {'positive' if net_profit > 0 else 'negative'}">${net_profit:+,.2f}</div>
            </div>
            <div class="card">
                <div class="card-label">Total Return</div>
                <div class="card-value {'positive' if total_return > 0 else 'negative'}">{total_return:+.2f}%</div>
            </div>
            <div class="card">
                <div class="card-label">Max Drawdown</div>
                <div class="card-value negative">{max_dd:.2f}%</div>
            </div>
            <div class="card">
                <div class="card-label">Profit Factor</div>
                <div class="card-value">{profit_factor:.2f}</div>
            </div>
            <div class="card">
                <div class="card-label">Win Rate</div>
                <div class="card-value">{win_rate:.1f}%</div>
            </div>
            <div class="card">
                <div class="card-label">Total Trades</div>
                <div class="card-value">{total_trades}</div>
            </div>
            <div class="card">
                <div class="card-label">Sharpe (Smart)</div>
                <div class="card-value">{metrics.get('smart_sharpe', 'N/A'):.3f}</div>
            </div>
            <div class="card">
                <div class="card-label">Time in Market</div>
                <div class="card-value">{metrics.get('time_in_market', 0)*100:.1f}%</div>
            </div>
        </div>
        
        <div class="chart">{fig.to_html(full_html=False, include_plotlyjs=False)}</div>
        
        <div class="card" style="margin-top: 20px;">
            <h3>Configuration</h3>
            <table>
                <tr><th>Parameter</th><th>Value</th></tr>
                <tr><td>Strategy</td><td>{run_config.get('strategy', 'N/A')}</td></tr>
                <tr><td>Data Path</td><td>{run_config.get('data_path', 'N/A')}</td></tr>
                <tr><td>Date Range</td><td>{run_config.get('start', 'N/A')} to {run_config.get('end', 'N/A')}</td></tr>
                <tr><td>Rows Used</td><td>{run_config.get('rows_used', 'N/A')}</td></tr>
                <tr><td>Fee Rate</td><td>{run_config.get('fee_rate', 0)}</td></tr>
            </table>
        </div>
"""
    
    # Add trades table if available
    if trades is not None and not trades.is_empty():
        trade_rows = trades.head(50).to_dicts()
        html += '''
        <div class="card" style="margin-top: 20px;">
            <h3>Recent Trades (Top 50)</h3>
            <table>
                <tr><th>Entry Time</th><th>Exit Time</th><th>Side</th><th>Entry Price</th><th>Exit Price</th><th>P&L</th></tr>
'''
        for t in trade_rows:
            pnl = t.get("pnl", 0)
            pnl_class = "positive" if pnl > 0 else "negative" if pnl < 0 else ""
            side = "Long" if t.get("side", 0) == 1 else "Short"
            html += f'''                <tr>
                    <td>{t.get('entry_time', 'N/A')}</td>
                    <td>{t.get('exit_time', 'N/A')}</td>
                    <td>{side}</td>
                    <td>{t.get('entry_price', 'N/A'):.4f}</td>
                    <td>{t.get('exit_price', 'N/A'):.4f}</td>
                    <td class="{pnl_class}">{pnl:+.4f}</td>
                </tr>
'''
        html += '''            </table>
        </div>
'''
    
    html += '''
    </div>
</body>
</html>'''
    
    with open(output_path, "w") as f:
        f.write(html)
    
    return output_path


def _should_generate_html_report(gate_result: PipelineGateResult, config: GateConfig) -> bool:
    """Determine if HTML report should be generated based on gate result and policy."""
    if config.report_policy == ReportPolicy.ALWAYS:
        return True
    if config.report_policy == ReportPolicy.NEVER:
        return False
    return gate_result.passed


def _write_failure_report(gate_result: PipelineGateResult, run_config: dict, output_dir: Path) -> Path:
    """Write failure report for strategies that don't pass the gate."""
    failure_path = output_dir / "failure_report.md"
    
    lines = [
        "# Backtest Failed Pipeline Gate",
        "",
        f"**Status:** FAILED",
        f"**Stage:** {gate_result.stage}",
        "",
        "## Failed Criteria",
    ]
    
    for reason in gate_result.reasons:
        lines.append(f"- {reason}")
    
    if gate_result.warnings:
        lines.append("")
        lines.append("## Warnings")
        for warning in gate_result.warnings:
            lines.append(f"- {warning}")
    
    lines.append("")
    lines.append("## Key Metrics")
    for key, value in gate_result.metrics.items():
        if value is not None:
            if isinstance(value, float):
                lines.append(f"- **{key}:** {value:.4f}")
            else:
                lines.append(f"- **{key}:** {value}")
    
    lines.append("")
    lines.append("## Configuration Used")
    lines.append(f"- Strategy: {run_config.get('strategy', 'N/A')}")
    lines.append(f"- Data: {run_config.get('data_path', 'N/A')}")
    lines.append(f"- Range: {run_config.get('start', 'N/A')} to {run_config.get('end', 'N/A')}")
    
    with open(failure_path, "w") as f:
        f.write("\n".join(lines))
    
    return failure_path


def _extract_trades(frame: pl.DataFrame) -> pl.DataFrame | None:
    """Extract trade records from backtest result frame.
    
    Args:
        frame: DataFrame with timestamp, position, equity, close columns
        
    Returns:
        DataFrame with trade records or None if no trades
    """
    if "position" not in frame.columns:
        return None
    
    df = frame.sort("timestamp").select(["timestamp", "position", "equity", "close"])
    rows = df.to_dicts()
    
    trades = []
    in_position = False
    entry_time = None
    entry_price = None
    
    for i, row in enumerate(rows):
        ts = row["timestamp"]
        pos = float(row["position"])
        close = float(row["close"])
        
        if pos > 0 and not in_position:
            # Entered position
            in_position = True
            entry_time = ts
            entry_price = close
        elif pos == 0 and in_position:
            # Exited position
            in_position = False
            exit_time = ts
            exit_price = close
            pnl = (exit_price - entry_price) / entry_price if entry_price > 0 else 0
            side = 1  # Assume long for now
            
            trades.append({
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "side": side,
            })
    
    if not trades:
        return None
    
    return pl.DataFrame(trades)


__all__ = ["write_backtest_artifacts", "render_backtest_report"]