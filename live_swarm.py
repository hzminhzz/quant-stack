"""
live_swarm.py — Unified Actor-Critic Multi-Agent Swarm
======================================================
The SINGLE production entry point for strategy validation.

Pipeline: discovery.py → research.py → live_swarm.py → execution.py

Features:
- Dependency Injection via engine.deps (persistent DuckDB + CCXT)
- 3-Phase validation: In-Sample → Monte Carlo → Out-Of-Sample
- Hardened CRO with ghost-alpha detection and statistical significance checks
- Detailed institutional-grade reporting (CAGR, DD, Sharpe, Tail, Kelly, Trades)
- Optional LanceDB signal seeding from discovery.py
"""
import argparse
import asyncio
import json
import warnings
from pathlib import Path

import numpy as np
import polars as pl
from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from engine.deps import QuantFactoryDeps, create_deps
from engine.analytics_pro import calculate_prop_metrics
from engine.monte_carlo import run_monte_carlo
from engine.schemas import PropFirmContract
from pipeline_artifacts import DEFAULT_SIGNAL_ARTIFACT_PATH, ValidationArtifact, load_signal_artifact, save_validation_artifact
from strategy_families import available_strategy_families, get_strategy_family
from strategy_families.base import StrategyProposal


# ═══════════════════════════════════════════════════════════════
#  SCHEMAS
# ═══════════════════════════════════════════════════════════════

class RobustnessCritique(BaseModel):
    is_robust: bool = Field(
        ...,
        description="True ONLY if ALL checks pass. False if ANY check fails."
    )
    critique: str = Field(
        ...,
        description="Specific critique referencing exact numbers from the payload."
    )


# ═══════════════════════════════════════════════════════════════
#  PROVIDERS & MODELS (Fallback Logic)
# ═══════════════════════════════════════════════════════════════

# Primary: DeepSeek (High Performance)
deepseek_provider = OpenAIProvider(
    base_url="https://api.deepseek.com", 
    api_key="sk-44c79a5a04494c1788ccd723ac565166" # USER: Replace with actual key or env var
)
primary_model = OpenAIChatModel("deepseek-chat", provider=deepseek_provider)

# Fallback: Local / OpenAI (Reliability)
local_provider = OpenAIProvider(base_url="http://127.0.0.1:8000/v1", api_key="anything")
fallback_model = OpenAIChatModel("gpt-5.4", provider=local_provider)


async def run_agent_with_fallback(agent, prompt, deps=None, history=None):
    """Execution wrapper with automatic model fallback."""
    print(f"📡 Requesting {primary_model.model_name}...")
    try:
        # Try Primary
        result = await agent.run(prompt, deps=deps, message_history=history, model=primary_model)
        print(f"✅ {primary_model.model_name} Success.")
        return result
    except Exception as e:
        print(f"❌ Primary model ({primary_model.model_name}) FAILED.")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error Details: {str(e)}")
        
        if "429" in str(e) or "limit" in str(e).lower():
            print("   (Primary hit rate limit - likely fallback will too if local)")
            
        print(f"🔄 Falling back to {fallback_model.model_name}...")
        try:
            result = await agent.run(prompt, deps=deps, message_history=history, model=fallback_model)
            print(f"✅ {fallback_model.model_name} Success.")
            return result
        except Exception as e2:
            print(f"❌ Fallback model ({fallback_model.model_name}) ALSO FAILED.")
            print(f"   Error Details: {str(e2)}")
            raise e2


# ═══════════════════════════════════════════════════════════════
#  DEV AGENT (Actor)
# ═══════════════════════════════════════════════════════════════

dev_agent = Agent(
    fallback_model, # Initial model (can be overridden in run call)
    output_type=StrategyProposal,
    deps_type=QuantFactoryDeps,
    system_prompt=(
        "You are the Quant Dev. You MUST use the `get_market_context` tool first to understand "
        "the live orderbook before proposing parameters. Return a strategy_type and a params object "
        "that match the selected strategy family. Design for ROBUSTNESS and target 50+ trades in-sample."
    ),
)


@dev_agent.tool
def get_market_context(ctx: RunContext[QuantFactoryDeps]) -> str:
    """Check live orderbook depth and trade pressure to inform strategy parameters."""
    try:
        ob = ctx.deps.get_orderbook_snapshot("ETH/USDT", depth=20)
        trades = ctx.deps.get_recent_trades("ETH/USDT", limit=100)
        return (
            f"Live ETH/USDT Orderbook: Spread={ob['spread_pct']:.4f}%, "
            f"Bid Wall={ob['bid_wall_qty']:.1f} ETH, Ask Wall={ob['ask_wall_qty']:.1f} ETH. "
            f"Recent Trade Pressure: {trades['buy_pressure_pct']}% buys "
            f"({trades['buy_volume']:.2f} ETH bought vs {trades['sell_volume']:.2f} ETH sold). "
            f"Training data spans multi-year OHLCV candles."
        )
    except Exception as e:
        return f"Live market context unavailable ({e}). Use conservative parameters."


# ═══════════════════════════════════════════════════════════════
#  RISK AGENT (Critic) — HARDENED CRO
# ═══════════════════════════════════════════════════════════════

risk_agent = Agent(
    fallback_model,
    output_type=RobustnessCritique,
    system_prompt=(
        "You are the Chief Risk Officer (CRO). Evaluate the robustness payload STRICTLY.\n\n"
        "HARD RULES (automatic REJECT if ANY fail):\n"
        "1. SANITY CHECK: REJECT if Monte Carlo DD is 0.0% or In-Sample CAGR is exactly 0.0%.\n"
        "   This indicates ZERO trades, ghost alpha, or a degenerate backtest.\n"
        "2. TRADE COUNT: REJECT if total trades < 20. Insufficient statistical significance.\n"
        "3. IN-SAMPLE CAGR: Must be > 0% (positive alpha required).\n"
        "4. MONTE CARLO: abs(MC 95th percentile DD) MUST be < 16%.\n"
        "5. REGIME CHECK: Out-Of-Sample CAGR must be > -5%.\n"
        "6. SHARPE CHECK: In-Sample Smart Sharpe should be > 0.3 for meaningful edge.\n\n"
        "SOFT WARNINGS (note but don't auto-reject):\n"
        "- Infinite tail ratio or gain/pain ratio = likely sparse trades\n"
        "- OOS Sharpe negative while IS Sharpe positive = possible curve fitting\n\n"
        "Drawdowns are expressed as NEGATIVE numbers. Evaluate using ABSOLUTE VALUE.\n"
        "Be brutally honest. Do not approve 'too perfect' results."
    ),
)


# ═══════════════════════════════════════════════════════════════
#  DETAILED REPORTING
# ═══════════════════════════════════════════════════════════════

def run_backtest_phase(close_prices, df, family, params, label):
    """Run a single backtest phase with full institutional reporting."""
    equity, exposed, trades = family.simulate(close_prices, params)

    df_m = df.with_columns([
        (pl.Series("equity", equity) * 10000.0), # $10k initial
        pl.Series("is_exposed", exposed)
    ])
    metrics = calculate_prop_metrics(df_m, initial_capital=10000.0)

    print(f"\n📊 [{label}] Detailed Metrics")
    print(f"  ├─ CAGR:              {metrics.get('cagr', 0) * 100:>8.2f}%")
    print(f"  ├─ Max Drawdown:      {metrics.get('max_drawdown', 0) * 100:>8.2f}%")
    print(f"  ├─ Max Daily DD:      {metrics.get('max_daily_drawdown', 0) * 100:>8.2f}%")
    print(f"  ├─ Smart Sharpe:      {metrics.get('smart_sharpe', 0):>8.3f}")
    print(f"  ├─ Smart Sortino:     {metrics.get('smart_sortino', 0):>8.3f}")
    print(f"  ├─ Tail Ratio:        {metrics.get('tail_ratio', 0):>8.3f}")
    print(f"  ├─ Gain/Pain Ratio:   {metrics.get('gain_pain_ratio', 0):>8.3f}")
    print(f"  ├─ Kelly Criterion:   {metrics.get('kelly_criterion', 0):>8.3f}")
    print(f"  └─ Trades:            {len(trades):>8d}")

    return metrics, trades


def build_cro_payload(is_metrics, oos_metrics, mc_95, is_trades, oos_trades):
    """Build the full payload for the CRO with all metrics + trade counts."""

    def safe_metrics(m):
        return {k: (float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v)
                for k, v in m.items()}

    return {
        "in_sample_metrics": safe_metrics(is_metrics),
        "in_sample_trade_count": int(len(is_trades)),
        "out_of_sample_metrics": safe_metrics(oos_metrics),
        "out_of_sample_trade_count": int(len(oos_trades)),
        "monte_carlo_95_dd_absolute_pct": round(abs(mc_95) * 100, 2),
        "note": "Monte Carlo passes if absolute value < 16%. Reject if 0.0% (ghost alpha).",
    }


def validate_phase_metrics(metrics: dict, label: str) -> str | None:
    try:
        PropFirmContract(**metrics)
    except ValidationError as exc:
        return f"{label} failed deterministic prop-firm validation: {exc.errors()[0]['msg']}"
    return None


# ═══════════════════════════════════════════════════════════════
#  CLI ARGS
# ═══════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(description="Quant Factory — Live Swarm Validator")
    parser.add_argument("--family", choices=available_strategy_families(), default="bb",
                        help="Strategy family to optimize")
    parser.add_argument("--asset", default="ETH", help="Asset to validate (ETH, BTC, BNB)")
    parser.add_argument("--train-years", nargs="+", type=int, default=[2021, 2022, 2023],
                        help="Training years")
    parser.add_argument("--test-years", nargs="+", type=int, default=[2024],
                        help="Out-of-sample years")
    parser.add_argument("--max-iterations", type=int, default=4,
                        help="Max swarm refinement iterations")
    parser.add_argument("--signal", action="store_true",
                        help="Seed from discovered LanceDB signal instead of letting Dev propose freely")
    parser.add_argument("--mc-seed", type=int, default=42,
                        help="Deterministic seed for Monte Carlo stress testing")
    parser.add_argument("--artifact-path", default="artifacts/latest_validation.json",
                        help="Path to write validation artifact JSON")
    parser.add_argument("--signal-artifact-path", default=str(DEFAULT_SIGNAL_ARTIFACT_PATH),
                        help="Path to input signal artifact JSON used for seeding")
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

async def main():
    warnings.filterwarnings("ignore")
    args = parse_args()
    family = get_strategy_family(args.family)

    all_years = args.train_years + args.test_years
    split_date = f"{args.test_years[0]}-01-01"

    print("=" * 70)
    print("  QUANT FACTORY — UNIFIED MULTI-AGENT SWARM")
    print("=" * 70)

    # ── ONE-TIME SETUP ──
    deps = create_deps()

    print(f"\n📂 Loading {args.asset} data ({args.train_years} train, {args.test_years} OOS)...")
    
    # We load everything via DuckDB glob for more flexibility
    years_all = list(set(args.train_years + args.test_years))
    file_patterns = [f"'Data/Binance/{args.asset}_{family.raw_data_timeframe}_{y}.parquet'" for y in years_all]
    
    # Cast timestamp to datetime at the query level
    union_query = " UNION ALL ".join([
        f"SELECT epoch_ms(timestamp) as timestamp, open, high, low, close, volume FROM read_parquet({p})" 
        for p in file_patterns
    ])
    raw_df = deps.db.sql(f"SELECT * FROM ({union_query}) ORDER BY timestamp ASC").pl()

    # Split and Resample
    train_raw = raw_df.filter(pl.col("timestamp").dt.year().is_in(args.train_years))
    test_raw = raw_df.filter(pl.col("timestamp").dt.year().is_in(args.test_years))
    
    train_df = family.prepare_market_data(train_raw)
    test_df = family.prepare_market_data(test_raw)

    train_close = train_df["close"].to_numpy()
    test_close = test_df["close"].to_numpy()

    print(f"  -> In-Sample (Train): {len(train_df)} bars ({family.validation_timeframe})")
    print(f"  -> Out-Of-Sample:     {len(test_df)} bars ({family.validation_timeframe})")

    print("\n✅ Data Loading Complete. Starting Swarm Loop...")

    # ── OPTIONAL: SEED FROM DISCOVERED SIGNAL ──
    seed_info = ""
    if args.signal:
        try:
            signal_artifact = load_signal_artifact(path=Path(args.signal_artifact_path))
            if signal_artifact.strategy_type != family.name:
                print(
                    f"  ❌ Signal artifact family mismatch: selected '{family.name}' but artifact is '{signal_artifact.strategy_type}'."
                )
                deps.db.close()
                return
            print(f"\n📡 Seeding from signal artifact (source: {signal_artifact.source}):")
            print(f"  family={signal_artifact.strategy_type}, signal={signal_artifact.signal}")
            seed_info = family.build_seed_hint(signal_artifact.signal)
        except Exception as e:
            print(f"  ⚠️ Could not load signal artifact: {e}. Dev will propose freely.")

    # ── SWARM LOOP ──
    max_iterations = args.max_iterations
    iteration = 0
    dev_history = []
    critique = None
    initial_prompt = family.build_initial_prompt(seed_info)

    while iteration < max_iterations:
        print(f"\n{'=' * 70}")
        print(f"  SWARM ITERATION {iteration + 1}/{max_iterations}")
        print(f"{'=' * 70}")

        # ── ACTOR: Dev Agent proposes parameters ──
        print("🤖 [Quant Dev]: Consulting live market context...")
        if iteration == 0:
            prompt = initial_prompt
        else:
            prompt = (
                family.build_retry_prompt(critique.critique)
            )

        dev_result = await run_agent_with_fallback(
            dev_agent, prompt, deps=deps, history=dev_history
        )
        dev_history = dev_result.all_messages()
        strategy = getattr(dev_result, "output", getattr(dev_result, "data", None))
        if not strategy:
            print("  ❌ Error: Could not extract strategy from dev agent.")
            break

        if strategy.strategy_type != family.name:
            critique = RobustnessCritique(
                is_robust=False,
                critique=f"Strategy family mismatch: expected '{family.name}', got '{strategy.strategy_type}'.",
            )
            print(f"\n  ❌ Robust: False")
            print(f"  📋 Verdict: {critique.critique}")
            iteration += 1
            continue

        try:
            params = family.validate_params(strategy.params)
        except ValidationError as exc:
            critique = RobustnessCritique(
                is_robust=False,
                critique=f"Invalid strategy parameters: {exc.errors()[0]['msg']}",
            )
            print(f"\n  ❌ Robust: False")
            print(f"  📋 Verdict: {critique.critique}")
            iteration += 1
            continue

        print(f"  -> Family: {family.name}")
        print(f"  -> Params: {family.format_params(params)}")
        print(f"  -> Rationale: {strategy.rationale}")

        # ── PHASE 1: In-Sample Backtest ──
        print(f"\n⚙️  [Phase 1]: In-Sample Backtest ({args.train_years})...")
        is_metrics, is_trades = run_backtest_phase(
            train_close, train_df, family, params, "In-Sample",
        )

        deterministic_rejection = validate_phase_metrics(is_metrics, "In-Sample")
        if deterministic_rejection:
            print(f"\n  ❌ Robust: False")
            print(f"  📋 Verdict: {deterministic_rejection}")
            critique = RobustnessCritique(is_robust=False, critique=deterministic_rejection)
            iteration += 1
            continue

        # ── PHASE 2: Monte Carlo Stress Test ──
        print(f"\n🎲 [Phase 2]: Monte Carlo Stress Test (1,000 shuffles)...")
        mc_95, mc_50 = run_monte_carlo(is_trades, num_simulations=1000, seed=args.mc_seed)
        print(f"  -> 95th Percentile Worst-Case DD: {mc_95 * 100:.2f}%")
        print(f"  -> Median DD across simulations:  {mc_50 * 100:.2f}%")

        # ── PHASE 3: Out-Of-Sample Backtest ──
        print(f"\n🔮 [Phase 3]: Out-Of-Sample Backtest ({args.test_years})...")
        oos_metrics, oos_trades = run_backtest_phase(
            test_close, test_df, family, params, "Out-Of-Sample",
        )

        deterministic_rejection = validate_phase_metrics(oos_metrics, "Out-Of-Sample")
        if deterministic_rejection:
            print(f"\n  ❌ Robust: False")
            print(f"  📋 Verdict: {deterministic_rejection}")
            critique = RobustnessCritique(is_robust=False, critique=deterministic_rejection)
            iteration += 1
            continue

        # ── CRITIC: CRO Evaluates ──
        print("\n👔 [CRO]: Evaluating Full Robustness Report...")
        payload = build_cro_payload(is_metrics, oos_metrics, mc_95, is_trades, oos_trades)
        risk_result = await run_agent_with_fallback(risk_agent, json.dumps(payload))
        critique = getattr(risk_result, "output", getattr(risk_result, "data", None))
        if not critique:
            print("  ❌ Error: Could not extract critique from risk agent.")
            break

        print(f"\n  {'✅' if critique.is_robust else '❌'} Robust: {critique.is_robust}")
        print(f"  📋 Verdict: {critique.critique}")

        if critique.is_robust:
            artifact = ValidationArtifact(
                strategy_type=family.name,
                params=params.model_dump(),
                rationale=strategy.rationale,
                in_sample_metrics=payload["in_sample_metrics"],
                in_sample_trade_count=payload["in_sample_trade_count"],
                out_of_sample_metrics=payload["out_of_sample_metrics"],
                out_of_sample_trade_count=payload["out_of_sample_trade_count"],
                monte_carlo_95_dd_absolute_pct=payload["monte_carlo_95_dd_absolute_pct"],
                monte_carlo_median_dd_absolute_pct=round(abs(mc_50) * 100, 2),
                approved=True,
                critique=critique.critique,
            )
            save_validation_artifact(artifact, path=__import__("pathlib").Path(args.artifact_path))
            print(f"\n{'=' * 70}")
            print("  🎉  ALPHA CONFIRMED — INSTITUTIONAL GRADE STRATEGY FOUND!")
            print(f"  Family     : {family.name}")
            print(f"  Params     : {family.format_params(params)}")
            print(f"  Artifact   : {args.artifact_path}")
            print(f"{'=' * 70}")
            break

        iteration += 1

    if iteration == max_iterations:
        print(f"\n❌ Swarm exhausted {max_iterations} iterations without approval.")

    # Cleanup
    deps.db.close()
    print("\n🔌 DuckDB connection closed. Pipeline complete.")


if __name__ == "__main__":
    asyncio.run(main())
