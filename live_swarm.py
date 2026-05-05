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
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from engine.deps import QuantFactoryDeps, create_deps
from engine.evaluator import (
    BacktestPhaseResult,
    DeterministicEvaluationRequest,
    DeterministicEvaluationResult,
    evaluate_candidate,
    load_market_frames,
    MarketFrameLoadRequest,
)
from evolution.experience_pool import create_evolution_run, insert_experience_entry, insert_failure_event, update_evolution_run
from evolution.schemas import EvolutionRun, ExperienceEntry, FailureEvent
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


def print_phase_metrics(phase: BacktestPhaseResult) -> None:
    metrics = phase.metrics
    print(f"\n📊 [{phase.label}] Detailed Metrics")
    print(f"  ├─ CAGR:              {metrics.get('cagr', 0) * 100:>8.2f}%")
    print(f"  ├─ Max Drawdown:      {metrics.get('max_drawdown', 0) * 100:>8.2f}%")
    print(f"  ├─ Max Daily DD:      {metrics.get('max_daily_drawdown', 0) * 100:>8.2f}%")
    print(f"  ├─ Smart Sharpe:      {metrics.get('smart_sharpe', 0):>8.3f}")
    print(f"  ├─ Smart Sortino:     {metrics.get('smart_sortino', 0):>8.3f}")
    print(f"  ├─ Tail Ratio:        {metrics.get('tail_ratio', 0):>8.3f}")
    print(f"  ├─ Gain/Pain Ratio:   {metrics.get('gain_pain_ratio', 0):>8.3f}")
    print(f"  ├─ Kelly Criterion:   {metrics.get('kelly_criterion', 0):>8.3f}")
    print(f"  └─ Trades:            {len(phase.trades):>8d}")


class AttemptOutcome(str, Enum):
    FAMILY_MISMATCH = "family_mismatch"
    PARAM_VALIDATION_FAILED = "param_validation_failed"
    DETERMINISTIC_REJECTION = "deterministic_rejection"
    CRO_REJECTED = "cro_rejected"
    APPROVED = "approved"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe_metrics(metrics: dict[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in metrics.items():
        if isinstance(value, bool):
            safe[key] = value
        elif isinstance(value, int):
            safe[key] = value
        elif isinstance(value, float):
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe


def _candidate_name(iteration: int) -> str:
    return f"swarm-iteration-{iteration + 1}"


def _build_run_metadata(args: argparse.Namespace) -> dict[str, object]:
    return {
        "asset": args.asset,
        "train_years": list(args.train_years),
        "test_years": list(args.test_years),
        "max_iterations": args.max_iterations,
        "mc_seed": args.mc_seed,
        "signal_seeded": args.signal,
        "artifact_path": args.artifact_path,
    }


def _build_evolution_run(args: argparse.Namespace, strategy_type: str) -> EvolutionRun:
    return EvolutionRun(
        run_id=f"live-swarm-{uuid4().hex}",
        objective="Validate live swarm candidate robustness",
        strategy_type=strategy_type,
        status="running",
        metadata=_build_run_metadata(args),
    )


def _build_evaluation_summary(evaluation: DeterministicEvaluationResult) -> dict[str, object]:
    summary: dict[str, object] = {
        "in_sample_metrics": _json_safe_metrics(evaluation.in_sample.metrics),
        "in_sample_trade_count": len(evaluation.in_sample.trades),
    }
    if evaluation.monte_carlo is not None:
        summary["monte_carlo_95_dd_absolute_pct"] = round(abs(evaluation.monte_carlo.dd_95) * 100, 2)
        summary["monte_carlo_median_dd_absolute_pct"] = round(abs(evaluation.monte_carlo.dd_50) * 100, 2)
    if evaluation.out_of_sample is not None:
        summary["out_of_sample_metrics"] = _json_safe_metrics(evaluation.out_of_sample.metrics)
        summary["out_of_sample_trade_count"] = len(evaluation.out_of_sample.trades)
    if evaluation.deterministic_rejection is not None:
        summary["deterministic_rejection"] = evaluation.deterministic_rejection
    return summary


class ExperienceLogger:
    def __init__(self, db, run: EvolutionRun) -> None:
        self._db = db
        self.run = run

    @classmethod
    def create(cls, db, args: argparse.Namespace, strategy_type: str) -> "ExperienceLogger":
        run = _build_evolution_run(args, strategy_type)
        create_evolution_run(db, run)
        return cls(db=db, run=run)

    def finalize(self, *, status: str, metadata_updates: dict[str, object] | None = None) -> EvolutionRun:
        metadata = dict(self.run.metadata)
        if metadata_updates is not None:
            metadata.update(metadata_updates)
        self.run = self.run.model_copy(
            update={
                "status": status,
                "completed_at": _utc_now(),
                "metadata": metadata,
            }
        )
        update_evolution_run(self._db, self.run)
        return self.run

    def record_attempt(
        self,
        *,
        iteration: int,
        strategy: StrategyProposal,
        outcome: AttemptOutcome,
        details: dict[str, object],
    ) -> str:
        experience_id = f"exp-{uuid4().hex}"
        entry = ExperienceEntry(
            experience_id=experience_id,
            run_id=self.run.run_id,
            strategy_type=self.run.strategy_type,
            candidate_name=_candidate_name(iteration),
            hypothesis=strategy.rationale,
            metrics={
                "iteration": iteration + 1,
                "outcome": outcome.value,
            },
            artifacts={
                "strategy_type": strategy.strategy_type,
                "params": strategy.params,
                "details": details,
            },
            notes=f"Live swarm attempt logged as {outcome.value}",
        )
        insert_experience_entry(self._db, entry)
        return experience_id

    def record_failure(
        self,
        *,
        experience_id: str | None,
        stage: str,
        failure_type: str,
        message: str,
        details: dict[str, object],
    ) -> None:
        insert_failure_event(
            self._db,
            FailureEvent(
                event_id=f"fail-{uuid4().hex}",
                run_id=self.run.run_id,
                experience_id=experience_id,
                stage=stage,
                failure_type=failure_type,
                message=message,
                details=details,
            ),
        )


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
    parser.add_argument("--log-experience", action="store_true",
                         help="Persist passive live swarm experience logs to DuckDB")
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

async def main():
    warnings.filterwarnings("ignore")
    args = parse_args()
    family = get_strategy_family(args.family)

    print("=" * 70)
    print("  QUANT FACTORY — UNIFIED MULTI-AGENT SWARM")
    print("=" * 70)

    # ── ONE-TIME SETUP ──
    deps = create_deps()
    experience_logger = ExperienceLogger.create(deps.db, args, family.name) if args.log_experience else None

    print(f"\n📂 Loading {args.asset} data ({args.train_years} train, {args.test_years} OOS)...")
    market_frames = load_market_frames(
        deps=deps,
        family=family,
        request=MarketFrameLoadRequest(
            asset=args.asset,
            train_years=args.train_years,
            test_years=args.test_years,
        ),
    )

    print(f"  -> In-Sample (Train): {len(market_frames.train_df)} bars ({family.validation_timeframe})")
    print(f"  -> Out-Of-Sample:     {len(market_frames.test_df)} bars ({family.validation_timeframe})")

    print("\n✅ Data Loading Complete. Starting Swarm Loop...")

    # ── OPTIONAL: SEED FROM DISCOVERED SIGNAL ──
    seed_info = ""
    if args.signal:
        try:
            signal_artifact = load_signal_artifact(path=Path(args.signal_artifact_path))
            if signal_artifact.strategy_type != family.name:
                if experience_logger is not None:
                    experience_logger.record_failure(
                        experience_id=None,
                        stage="signal_seed",
                        failure_type="family_mismatch",
                        message="Signal artifact family mismatch.",
                        details={
                            "expected_family": family.name,
                            "artifact_family": signal_artifact.strategy_type,
                        },
                    )
                print(
                    f"  ❌ Signal artifact family mismatch: selected '{family.name}' but artifact is '{signal_artifact.strategy_type}'."
                )
                if experience_logger is not None:
                    experience_logger.finalize(
                        status="failed",
                        metadata_updates={
                            "final_outcome": "signal_artifact_family_mismatch",
                            "approved": False,
                        },
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
            assert critique is not None
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
            if experience_logger is not None:
                experience_id = experience_logger.record_attempt(
                    iteration=iteration,
                    strategy=strategy,
                    outcome=AttemptOutcome.FAMILY_MISMATCH,
                    details={
                        "expected_family": family.name,
                        "actual_family": strategy.strategy_type,
                    },
                )
                experience_logger.record_failure(
                    experience_id=experience_id,
                    stage="proposal",
                    failure_type="family_mismatch",
                    message="Strategy family mismatch.",
                    details={
                        "expected_family": family.name,
                        "actual_family": strategy.strategy_type,
                    },
                )
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
            if experience_logger is not None:
                experience_id = experience_logger.record_attempt(
                    iteration=iteration,
                    strategy=strategy,
                    outcome=AttemptOutcome.PARAM_VALIDATION_FAILED,
                    details={
                        "validation_errors": exc.errors(),
                    },
                )
                experience_logger.record_failure(
                    experience_id=experience_id,
                    stage="proposal",
                    failure_type="param_validation_failed",
                    message="Strategy parameters failed validation.",
                    details={
                        "validation_errors": exc.errors(),
                    },
                )
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

        # ── DETERMINISTIC EVALUATION ──
        print(f"\n⚙️  [Phase 1]: In-Sample Backtest ({args.train_years})...")
        evaluation = evaluate_candidate(
            DeterministicEvaluationRequest(
                family=family,
                params=params,
                train_close=market_frames.train_close,
                train_df=market_frames.train_df,
                test_close=market_frames.test_close,
                test_df=market_frames.test_df,
                mc_seed=args.mc_seed,
            )
        )
        print_phase_metrics(evaluation.in_sample)

        deterministic_rejection = evaluation.deterministic_rejection
        if evaluation.monte_carlo is None and deterministic_rejection:
            if experience_logger is not None:
                evaluation_summary = _build_evaluation_summary(evaluation)
                experience_id = experience_logger.record_attempt(
                    iteration=iteration,
                    strategy=strategy,
                    outcome=AttemptOutcome.DETERMINISTIC_REJECTION,
                    details={
                        "evaluation_summary": evaluation_summary,
                    },
                )
                experience_logger.record_failure(
                    experience_id=experience_id,
                    stage="deterministic_evaluation",
                    failure_type="deterministic_rejection",
                    message=deterministic_rejection,
                    details={
                        "evaluation_summary": evaluation_summary,
                    },
                )
            print(f"\n  ❌ Robust: False")
            print(f"  📋 Verdict: {deterministic_rejection}")
            critique = RobustnessCritique(is_robust=False, critique=deterministic_rejection)
            iteration += 1
            continue

        assert evaluation.monte_carlo is not None
        assert evaluation.out_of_sample is not None
        print(f"\n🎲 [Phase 2]: Monte Carlo Stress Test (1,000 shuffles)...")
        print(f"  -> 95th Percentile Worst-Case DD: {evaluation.monte_carlo.dd_95 * 100:.2f}%")
        print(f"  -> Median DD across simulations:  {evaluation.monte_carlo.dd_50 * 100:.2f}%")

        print(f"\n🔮 [Phase 3]: Out-Of-Sample Backtest ({args.test_years})...")
        print_phase_metrics(evaluation.out_of_sample)

        if deterministic_rejection:
            if experience_logger is not None:
                evaluation_summary = _build_evaluation_summary(evaluation)
                experience_id = experience_logger.record_attempt(
                    iteration=iteration,
                    strategy=strategy,
                    outcome=AttemptOutcome.DETERMINISTIC_REJECTION,
                    details={
                        "evaluation_summary": evaluation_summary,
                    },
                )
                experience_logger.record_failure(
                    experience_id=experience_id,
                    stage="deterministic_evaluation",
                    failure_type="deterministic_rejection",
                    message=deterministic_rejection,
                    details={
                        "evaluation_summary": evaluation_summary,
                    },
                )
            print(f"\n  ❌ Robust: False")
            print(f"  📋 Verdict: {deterministic_rejection}")
            critique = RobustnessCritique(is_robust=False, critique=deterministic_rejection)
            iteration += 1
            continue

        # ── CRITIC: CRO Evaluates ──
        print("\n👔 [CRO]: Evaluating Full Robustness Report...")
        assert evaluation.cro_payload is not None
        payload = evaluation.cro_payload.model_dump()
        risk_result = await run_agent_with_fallback(risk_agent, json.dumps(payload))
        critique = getattr(risk_result, "output", getattr(risk_result, "data", None))
        if not critique:
            print("  ❌ Error: Could not extract critique from risk agent.")
            break

        print(f"\n  {'✅' if critique.is_robust else '❌'} Robust: {critique.is_robust}")
        print(f"  📋 Verdict: {critique.critique}")

        artifact_run = None
        if experience_logger is not None:
            evaluation_summary = _build_evaluation_summary(evaluation)
            outcome = AttemptOutcome.APPROVED if critique.is_robust else AttemptOutcome.CRO_REJECTED
            experience_id = experience_logger.record_attempt(
                iteration=iteration,
                strategy=strategy,
                outcome=outcome,
                details={
                    "evaluation_summary": evaluation_summary,
                    "cro_verdict": critique.model_dump(mode="json"),
                    "approved": critique.is_robust,
                },
            )
            if critique.is_robust:
                artifact_run = experience_logger.finalize(
                    status="completed",
                    metadata_updates={
                        "final_outcome": "approved",
                        "approved": True,
                        "iterations_used": iteration + 1,
                    },
                )
            else:
                experience_logger.record_failure(
                    experience_id=experience_id,
                    stage="cro",
                    failure_type="cro_rejection",
                    message=critique.critique,
                    details={
                        "evaluation_summary": evaluation_summary,
                        "cro_verdict": critique.model_dump(mode="json"),
                    },
                )

        if critique.is_robust:
            artifact = ValidationArtifact(
                version="1.0",
                strategy_type=family.name,
                params=params.model_dump(),
                rationale=strategy.rationale,
                in_sample_metrics=payload["in_sample_metrics"],
                in_sample_trade_count=payload["in_sample_trade_count"],
                out_of_sample_metrics=payload["out_of_sample_metrics"],
                out_of_sample_trade_count=payload["out_of_sample_trade_count"],
                monte_carlo_95_dd_absolute_pct=payload["monte_carlo_95_dd_absolute_pct"],
                monte_carlo_median_dd_absolute_pct=round(abs(evaluation.monte_carlo.dd_50) * 100, 2),
                approved=True,
                critique=critique.critique,
                evolution_run=artifact_run,
            )
            save_validation_artifact(artifact, path=Path(args.artifact_path))
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
        if experience_logger is not None:
            experience_logger.finalize(
                status="failed",
                metadata_updates={
                    "final_outcome": "swarm_exhausted",
                    "approved": False,
                    "iterations_used": max_iterations,
                },
            )

    if experience_logger is not None and experience_logger.run.status == "running":
        experience_logger.finalize(
            status="failed",
            metadata_updates={
                "final_outcome": "unexpected_exit",
                "approved": False,
            },
        )

    # Cleanup
    deps.db.close()
    print("\n🔌 DuckDB connection closed. Pipeline complete.")


if __name__ == "__main__":
    asyncio.run(main())
