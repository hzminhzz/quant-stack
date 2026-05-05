"""Lightweight paper-context formatting helpers."""

from __future__ import annotations


def join_paper_context(items: list[str]) -> str:
    return "\n\n".join(item.strip() for item in items if item.strip())


__all__ = ["join_paper_context"]
