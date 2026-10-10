# Production evaluation preregistration

This file freezes the production evaluation protocol before any counted outcome.

The window starts at the commit that adds this file. Earlier paper-cycle refusals, research arms, and research holdouts are excluded. No result in this file is a performance claim.

## Rules

- Universe: NVDAUSDT, TSLAUSDT, AAPLUSDT, AMZNUSDT, MSFTUSDT, METAUSDT, GOOGLUSDT, COINUSDT, MSTRUSDT.
- Event: a qualifying SEC filing for the same instrument, with source URL, accession, filing time, fetch time, and content hash. Book observations are not events.
- Model: `prompts/decision_v2.txt` only, at most 3 production calls per day unless a higher cap is configured by name.
- Governor: the frozen vendor governor. It can only reduce or refuse.
- Entry: the next stored book after the proposal snapshot. The proposal book is not the fill book.
- Costs: stored book depth, spread, taker fee, and slippage. A missing book refuses.
- Exit: the configured horizon against the then-current book.
- Baselines: no-trade, and a random-abstention comparison once the sample exists.
- Primary metric: mean net basis points after costs. Secondary: median net basis points, closed-trade count, fees, and maximum drawdown.
- Minimum sample: 30 closed paper outcomes. Below that, the status is `INSUFFICIENT_DATA`.
- Labels: every future metric is `observed`, `estimated`, or `targeted`. This document records no observed returns.

## Current status

`INSUFFICIENT_DATA`. Sample size 0. Trading edge: inconclusive.
