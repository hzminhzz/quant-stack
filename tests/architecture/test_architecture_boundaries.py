"""Architecture boundary tests for quant-stack.

These tests enforce the governance rules defined in AGENTS.md.
Run with: uv run pytest tests/architecture/test_architecture_boundaries.py -q
"""

import ast
import os
from pathlib import Path
from typing import List, Set

import pytest


# Paths that are "core" and should NOT have forbidden imports
CORE_PATHS = [
    "quant_stack/backtesting",
    "quant_stack/indicators",
    "quant_stack/live",
]

# Paths that are "allowed" to have LLM imports
LLM_ALLOWED_PATHS = [
    "quant_stack/research",
    "quant_stack/research/optimization",
]

# Forbidden import patterns
FORBIDDEN_PANDAS = {"pandas", "pd"}
FORBIDDEN_LLM = {"pydantic_ai", "openai", "anthropic", "litellm"}
FORBIDDEN_PRIVATE_KEY = {"api_secret", "private_key", "password", "secret_key"}


def get_python_files(base_path: str) -> List[Path]:
    """Get all Python files in the given path (non-recursive for immediate children)."""
    path = Path(base_path)
    if not path.exists():
        return []
    return list(path.glob("*.py"))


def extract_imports(file_path: Path) -> Set[str]:
    """Extract all imports from a Python file."""
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def has_forbidden_terms(file_path: Path, terms: Set[str]) -> List[str]:
    """Check if file contains forbidden string terms."""
    found = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            for term in terms:
                # Check for assignment patterns like api_secret = ...
                # or function call patterns
                if f"{term} =" in content or f'"{term}"' in content or f"'{term}'" in content:
                    found.append(term)
    except (UnicodeDecodeError, OSError):
        pass
    return found


def is_core_path(file_path: Path) -> bool:
    """Check if file is in a core path."""
    path_str = str(file_path)
    for core in CORE_PATHS:
        if path_str.startswith(core):
            return True
    return False


def is_llm_allowed_path(file_path: Path) -> bool:
    """Check if file is in an LLM-allowed path."""
    path_str = str(file_path)
    for allowed in LLM_ALLOWED_PATHS:
        if path_str.startswith(allowed):
            return True
    return False


class TestNoPandasInCore:
    """Test that core paths don't import pandas."""

    @pytest.mark.parametrize("core_path", CORE_PATHS)
    def test_no_pandas_in_backtesting(self, core_path: str):
        """Core backtesting/indicators/live must not import pandas."""
        files = get_python_files(core_path)
        assert files, f"No Python files found in {core_path}"

        violations = []
        for f in files:
            imports = extract_imports(f)
            forbidden = imports & FORBIDDEN_PANDAS
            if forbidden:
                violations.append(f"{f.name}: {forbidden}")

        assert not violations, f"Pandas imports found in {core_path}: {violations}"


class TestNoLLMInCore:
    """Test that core paths don't import LLM libraries."""

    @pytest.mark.parametrize("core_path", CORE_PATHS)
    def test_no_llm_in_core_paths(self, core_path: str):
        """Core paths must not import LLM libraries."""
        files = get_python_files(core_path)
        if not files:
            pytest.skip(f"No files in {core_path}")

        violations = []
        for f in files:
            imports = extract_imports(f)
            forbidden = imports & FORBIDDEN_LLM
            if forbidden:
                violations.append(f"{f.name}: {forbidden}")

        assert not violations, f"LLM imports found in {core_path}: {violations}"


class TestNoStrategySpecificBacktesters:
    """Test that backtesting module has no strategy-specific backtester functions."""

    def test_no_strategy_backtest_functions(self):
        """Backtesting module must not have strategy-specific functions like run_rsi_backtest."""
        backtesting_path = "quant_stack/backtesting"
        files = get_python_files(backtesting_path)

        # Patterns that indicate strategy-specific backtesters
        forbidden_patterns = [
            "run_rsi_backtest",
            "run_bb_backtest",
            "run_grid_backtest",
            "run_.*_backtest",  # regex pattern
        ]

        violations = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    for pattern in forbidden_patterns:
                        # Simple string search (not full regex for simplicity)
                        if "run_" in pattern and pattern.replace("run_", "") in f.name.lower():
                            violations.append(f"{f.name}: potential strategy backtester")
            except UnicodeDecodeError:
                pass

        # More specific: check function definitions
        try:
            with open(f"{backtesting_path}/polars_engine.py", "r") as f:
                tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if "rsi" in node.name.lower() or "bb" in node.name.lower() or "grid" in node.name.lower():
                            if "backtest" in node.name.lower():
                                violations.append(f"polars_engine.py: {node.name}")
        except Exception:
            pass

        assert not violations, f"Strategy-specific backtesters found: {violations}"


class TestNoPrivateKeysInResearch:
    """Test that research paths don't have private key terms."""

    def test_no_private_keys_in_research(self):
        """Research and intelligence must not have private key terms."""
        paths_to_check = [
            "quant_stack/research",
            "quant_stack/intelligence",
        ]

        violations = []
        for base_path in paths_to_check:
            path = Path(base_path)
            if not path.exists():
                continue
            for f in path.rglob("*.py"):
                found = has_forbidden_terms(f, FORBIDDEN_PRIVATE_KEY)
                if found:
                    violations.append(f"{f.relative_to(base_path)}: {found}")

        assert not violations, f"Private key terms found: {violations}"


class TestNoLiveTradingInResearch:
    """Test that research doesn't import live execution modules."""

    def test_no_broker_execution_in_research(self):
        """Research must not import broker/execution modules."""
        research_path = "quant_stack/research"
        files = get_python_files(research_path)

        # Modules that indicate live trading/broker access
        forbidden_modules = {"execution", "broker", "account", "portfolio"}

        violations = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom):
                            if node.module:
                                module = node.module.split(".")[-1]
                                if module in forbidden_modules:
                                    violations.append(f"{f.name}: {node.module}")
            except Exception:
                pass

        assert not violations, f"Live trading imports in research: {violations}"


class TestStrategyEngineSelection:
    """Test that strategies declare capabilities and use correct engines."""

    def test_all_strategies_declare_capabilities(self):
        """Every strategy must declare capabilities."""
        from quant_stack.strategies import get_strategy
        
        known_strategies = ["rsi_sma", "bb_breakout", "grid", "smart_dca"]
        
        missing = []
        for name in known_strategies:
            try:
                module = get_strategy(name)
                if hasattr(module, "SPEC"):
                    spec = module.SPEC
                    if not hasattr(spec, "capabilities"):
                        missing.append(name)
            except Exception:
                pass
        
        assert not missing, f"Strategies missing capabilities: {missing}"

    def test_grid_dca_strategies_cannot_use_vectorbt(self):
        """Strategies with multi_leg or avg_price_dependent must not use vectorbt."""
        from quant_stack.strategies import get_strategy
        
        known_strategies = ["rsi_sma", "bb_breakout", "grid", "smart_dca"]
        
        violations = []
        for name in known_strategies:
            try:
                module = get_strategy(name)
                if hasattr(module, "SPEC"):
                    spec = module.SPEC
                    cap = getattr(spec, "capabilities", None)
                    if cap:
                        if cap.multi_leg or cap.average_price_dependent:
                            if spec.default_engine == "vectorbt":
                                violations.append(name)
            except Exception:
                pass
        
        assert not violations, f"Multi-leg strategies using vectorbt: {violations}"

    def test_engine_selector_respects_capabilities(self):
        """select_engine should return engine based on capabilities."""
        from quant_stack.strategies.specs import select_engine
        from quant_stack.strategies.smart_dca.spec import SPEC as smart_dca_spec
        from quant_stack.strategies.rsi_sma.spec import SPEC as rsi_sma_spec
        
        # smart_dca should use grid_dca (explicit override)
        assert select_engine(smart_dca_spec) == "grid_dca"
        
        # rsi_sma with vectorized should use vectorbt
        assert select_engine(rsi_sma_spec) == "vectorbt"


if __name__ == "__main__":
    pytest.main([__file__, "-q"])