# legacy/

This folder is for **deprecated or non-canonical systems** that are kept for compatibility, reference, or staged migration.

## Rule

Do not place new default workflows here.

If a feature belongs in the long-term architecture, it should live under `quant_stack/`.

## What belongs here

- old engines
- old strategy abstractions
- old validation scripts
- compatibility wrappers
- historical entrypoints kept temporarily during migration

## What does not belong here

- new reusable package code
- new canonical CLI flows
- new default backtest/report/optimization systems
