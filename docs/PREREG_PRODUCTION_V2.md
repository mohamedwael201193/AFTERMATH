# Production evaluation preregistration, version 2

This file freezes the S-A protocol before any counted S-A decision. It does not claim a trading edge.

Earlier research was negative or inconclusive. In a prior blinded replay, the model lost to the fixed-sign rule and to the model-off baseline. Those results stay frozen. This protocol tests a new hypothesis. It does not reopen a rejected one.

## Hypothesis

H-PROD-A. After an eligible 8-K Item 2.02 filing, the residual return of the listed stock perpetual versus a valid Nasdaq-100 reference may persist for 24 hours. The model's evidence-grounded LONG, SHORT, or NO_ACTION decision may beat a fixed-sign rule on the same events. This is a hypothesis, not an established result.

## Event and universe

- Counted events are 8-K Item 2.02 filings only, with an acceptance timestamp, accession, source URL, and content hash.
- Items 7.01 and 8.01 are shadow records. They are not counted events and they do not call the model.
- Universe: NVDAUSDT, TSLAUSDT, AAPLUSDT, AMZNUSDT, MSFTUSDT, METAUSDT, GOOGLUSDT, COINUSDT, MSTRUSDT.
- A filing is eligible only when its acceptance time is after the stored cursor and within 360 minutes.
- Missing or contradictory acceptance times are refused. Midnight on the filing date is not an event time.

## Decision

- Prompt: `prompts/decision_v3.txt`. The prompt hash and this file's hash are recorded on the receipt.
- The model may return LONG, SHORT, or NO_ACTION, with a thesis, invalidation, and cited evidence ids.
- Size is fixed at 5 percent of the 10,000 paper notional. Horizon is fixed at 24 hours. The model does not set either value.
- The frozen governor can shrink or refuse. It cannot be overridden by the model.
- Entry uses a later stored book, at least 60 minutes after acceptance when that book exists. The proposal book is not the fill book.
- Only candles whose close is at or before the decision time may enter the hedge calculation.

## Costs and exits

- Entry and exit walk the stored book.
- Fees use the contract taker fee when that field is present and valid.
- Funding uses the sourced rate and the position side. A missing rate is not replaced with a profitable zero.
- Exit is the 24-hour time stop or the registered max-loss stop, whichever comes first.

## Baselines

Each counted event records, on the same window and cost rules:

- the agent policy
- the fixed-sign rule
- the model-off policy
- a random-direction placebo
- a no-trade baseline

Research arms and old historical outcomes stay frozen and are not copied into this table.

## Verdict rule

A verdict needs at least 30 paired outcomes and at least 15 non-zero pairs. Below that, the status is `INSUFFICIENT_DATA`. One or two trades are not evidence of an edge.

The primary comparison is the paired agent result versus the fixed-sign rule, with a one-sided test and a paired bootstrap interval. Seeds are fixed before the sample is read.

Stop the counted strategy if cumulative agent net reaches -150 basis points, five consecutive governed losses occur, a fill is outside the stored book, a lifecycle record is unsigned, or the governor refuses every proposal across 10 or more complete proposals.

## Warm-up context

The frozen governor requires at least three observable Item 2.02 reactions before it can approve a new proposal. Those reactions may be recorded before the prospective window. A warm-up reaction can satisfy `n_precedents`. It is not a counted S-A outcome, and it does not enter the paired metric sample. If fewer than three stored reactions exist, the governor refuses `precedents_ok`. That count is never replaced with a constant.

## Current status

`INSUFFICIENT_DATA`. No counted S-A outcome exists under this protocol. Trading edge: inconclusive.
