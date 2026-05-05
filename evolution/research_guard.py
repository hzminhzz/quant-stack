from __future__ import annotations

import ast

from evolution.schemas import ResearchGuardCheck, ResearchGuardReport


REQUIRED_SIGNATURE = "def backtest_signal(df: pl.DataFrame) -> float"
DISALLOWED_IMPORT_ROOTS = {
    "aiohttp",
    "http",
    "httpx",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
DISALLOWED_CALL_PATTERNS = {
    "duckdb.connect",
    "os.popen",
    "os.system",
    "pathlib.Path.open",
    "pathlib.Path.read_bytes",
    "pathlib.Path.read_text",
    "pl.read_csv",
    "pl.read_ipc",
    "pl.read_json",
    "pl.read_parquet",
    "pl.scan_csv",
    "pl.scan_ipc",
    "pl.scan_parquet",
    "requests.get",
    "requests.post",
    "socket.socket",
    "subprocess.Popen",
    "subprocess.run",
}
DISALLOWED_CALL_NAMES = {"eval", "exec", "open", "__import__"}
ALLOWED_SOURCE_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}
FAMILY_DISALLOWED_TOKENS = {
    "rsi": {"upper_band", "lower_band", "middle_band", "bollinger", "bb_", "regime_sma"},
    "bb": {"rsi", "short_sma", "long_sma", "rsi_period", "rsi_threshold", "rsi_side"},
}


def guard_research_code(code: str, strategy_type: str | None = None) -> ResearchGuardReport:
    syntax_check = _build_syntax_check(code)
    if not syntax_check.passed:
        checks = {
            "syntax": syntax_check,
            "required_function": ResearchGuardCheck(passed=False, detail="Code must parse before the required function can be validated."),
            "disallowed_patterns": ResearchGuardCheck(passed=True, detail="Skipped because code did not parse."),
            "lookahead_bias": ResearchGuardCheck(passed=True, detail="Skipped because code did not parse."),
            "ohlcv_boundary": ResearchGuardCheck(passed=True, detail="Skipped because code did not parse."),
            "family_logic": ResearchGuardCheck(passed=True, detail="Skipped because code did not parse."),
        }
        return ResearchGuardReport(passed=False, summary=syntax_check.detail, checks=checks)

    tree = ast.parse(code)
    checks = {
        "syntax": syntax_check,
        "required_function": _build_required_function_check(tree),
        "disallowed_patterns": _build_disallowed_patterns_check(tree),
        "lookahead_bias": _build_lookahead_bias_check(tree),
        "ohlcv_boundary": _build_ohlcv_boundary_check(tree),
        "family_logic": _build_family_logic_check(code, strategy_type),
    }
    failures = [check.detail for check in checks.values() if not check.passed and check.detail]
    summary = failures[0] if failures else "Research code passed deterministic guard."
    return ResearchGuardReport(passed=not failures, summary=summary, checks=checks)


def _build_syntax_check(code: str) -> ResearchGuardCheck:
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return ResearchGuardCheck(passed=False, detail=f"Generated code is not valid Python: {exc.msg}.")
    return ResearchGuardCheck(passed=True, detail="Code parses successfully.")


def _build_required_function_check(tree: ast.AST) -> ResearchGuardCheck:
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "backtest_signal":
            continue
        if _has_required_signature(node):
            return ResearchGuardCheck(passed=True, detail="Matched required backtest function signature.")
        break
    return ResearchGuardCheck(passed=False, detail=f"Generated code must define `{REQUIRED_SIGNATURE}`.")


def _has_required_signature(node: ast.FunctionDef) -> bool:
    if node.args.posonlyargs or node.args.kwonlyargs or node.args.vararg or node.args.kwarg:
        return False
    if len(node.args.args) != 1:
        return False
    argument = node.args.args[0]
    if argument.arg != "df":
        return False
    if _annotation_to_string(argument.annotation) != "pl.DataFrame":
        return False
    return _annotation_to_string(node.returns) == "float"


def _build_disallowed_patterns_check(tree: ast.AST) -> ResearchGuardCheck:
    import_hits: list[str] = []
    call_hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", maxsplit=1)[0]
                if root_name in DISALLOWED_IMPORT_ROOTS:
                    import_hits.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            root_name = module_name.split(".", maxsplit=1)[0]
            if root_name in DISALLOWED_IMPORT_ROOTS:
                import_hits.append(module_name)
        elif isinstance(node, ast.Call):
            call_name = _call_to_string(node.func)
            if call_name in DISALLOWED_CALL_PATTERNS or call_name in DISALLOWED_CALL_NAMES:
                call_hits.append(call_name)
    if not import_hits and not call_hits:
        return ResearchGuardCheck(passed=True, detail="No obvious data-loading, shell, or network patterns detected.")

    hits = sorted(set(import_hits + call_hits))
    return ResearchGuardCheck(
        passed=False,
        detail="Disallowed pattern(s) detected: " + ", ".join(hits) + ".",
    )


def _build_lookahead_bias_check(tree: ast.AST) -> ResearchGuardCheck:
    negative_shift_hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_to_string(node.func).split(".")[-1] != "shift":
            continue
        if _call_has_negative_shift(node):
            negative_shift_hits.append(ast.unparse(node))
    if not negative_shift_hits:
        return ResearchGuardCheck(passed=True, detail="No obvious negative shift look-ahead detected.")

    return ResearchGuardCheck(
        passed=False,
        detail="Detected negative shift look-ahead primitive(s): " + ", ".join(sorted(set(negative_shift_hits))) + ".",
    )


def _build_ohlcv_boundary_check(tree: ast.AST) -> ResearchGuardCheck:
    alias_names = _collect_alias_names(tree)
    invalid_columns: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_to_string(node.func) != "pl.col":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        column_name = node.args[0].value
        if column_name in ALLOWED_SOURCE_COLUMNS or column_name in alias_names:
            continue
        invalid_columns.append(column_name)

    if not invalid_columns:
        return ResearchGuardCheck(passed=True, detail="No obvious non-OHLCV source column misuse detected.")

    return ResearchGuardCheck(
        passed=False,
        detail="Detected non-OHLCV or undefined column reference(s): " + ", ".join(sorted(set(invalid_columns))) + ".",
    )


def _build_family_logic_check(code: str, strategy_type: str | None) -> ResearchGuardCheck:
    normalized_family = (strategy_type or "").strip().lower()
    if normalized_family not in FAMILY_DISALLOWED_TOKENS:
        return ResearchGuardCheck(passed=True, detail="No family-specific logic guard configured.")

    lowered_code = code.lower()
    token_hits = [token for token in FAMILY_DISALLOWED_TOKENS[normalized_family] if token in lowered_code]
    if not token_hits:
        return ResearchGuardCheck(passed=True, detail=f"No obvious {normalized_family}-family logic mismatch detected.")

    return ResearchGuardCheck(
        passed=False,
        detail=(
            f"Detected logic tokens inconsistent with the {normalized_family} family: "
            + ", ".join(sorted(token_hits))
            + "."
        ),
    )


def _call_has_negative_shift(node: ast.Call) -> bool:
    if node.args and _is_negative_number(node.args[0]):
        return True
    for keyword in node.keywords:
        if keyword.arg in {"n", "periods"} and _is_negative_number(keyword.value):
            return True
    return False


def _is_negative_number(node: ast.AST) -> bool:
    return isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float))


def _collect_alias_names(tree: ast.AST) -> set[str]:
    alias_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_to_string(node.func).split(".")[-1] != "alias":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        alias_names.add(node.args[0].value)
    return alias_names


def _annotation_to_string(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    return ast.unparse(node)


def _call_to_string(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_to_string(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""
