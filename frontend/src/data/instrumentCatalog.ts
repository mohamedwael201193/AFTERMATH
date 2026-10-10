import type { InstrumentIdentity, DecisionState } from "@/types/domain";

/**
 * Illustrative instrument catalog for the preview workspace.
 *
 * These are representative tokenized instruments in the style of products
 * traded on Bitget. This list is explicitly illustrative — it is not a claim
 * that every symbol is currently listed on any venue.
 */

export interface CatalogEntry extends InstrumentIdentity {
  /** Current decision state shown in the explorer. */
  decisionState: DecisionState;
  /** Short human note shown on the token card. */
  note: string;
}

export const instrumentCatalog: CatalogEntry[] = [
  {
    symbol: "NVDA",
    name: "NVIDIA tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "NVIDIA Corporation",
    referenceSymbol: "NVDA (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "PROCEED",
    note: "Q3 results released after US cash close.",
  },
  {
    symbol: "TSLA",
    name: "Tesla tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "Tesla, Inc.",
    referenceSymbol: "TSLA (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "REJECT",
    note: "Supplier headline lacks primary confirmation.",
  },
  {
    symbol: "MSFT",
    name: "Microsoft tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "Microsoft Corporation",
    referenceSymbol: "MSFT (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "NO ACTION",
    note: "No qualifying events in the current window.",
  },
  {
    symbol: "META",
    name: "Meta Platforms tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "Meta Platforms, Inc.",
    referenceSymbol: "META (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "REJECT",
    note: "Headline conflicts with primary sources.",
  },
  {
    symbol: "AAPL",
    name: "Apple tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "Apple Inc.",
    referenceSymbol: "AAPL (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "NO ACTION",
    note: "Dividend record processed yesterday.",
  },
  {
    symbol: "AMZN",
    name: "Amazon tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "Amazon.com, Inc.",
    referenceSymbol: "AMZN (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "REDUCE",
    note: "Filing is confirmed; order-book depth is thin.",
  },
  {
    symbol: "GOOGL",
    name: "Alphabet tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "Alphabet Inc.",
    referenceSymbol: "GOOGL (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "NO ACTION",
    note: "No qualifying events in the current window.",
  },
  {
    symbol: "COIN",
    name: "Coinbase tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "Coinbase Global, Inc.",
    referenceSymbol: "COIN (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "WAIT",
    note: "Reference price is stale after a sharp move.",
  },
  {
    symbol: "QQQ",
    name: "Invesco QQQ Trust tokenized",
    kind: "INDEX_TOKEN",
    company: "Invesco QQQ Trust",
    referenceSymbol: "QQQ (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "WAIT",
    note: "Macro print waiting on cash-market open.",
  },
  {
    symbol: "SPY",
    name: "SPDR S&P 500 ETF tokenized",
    kind: "INDEX_TOKEN",
    company: "SPDR S&P 500 ETF Trust",
    referenceSymbol: "SPY (NYSE Arca)",
    venue: "Bitget · tokenized",
    decisionState: "NO ACTION",
    note: "No qualifying events in the current window.",
  },
  {
    symbol: "MU",
    name: "Micron tokenized stock",
    kind: "EQUITY_TOKEN",
    company: "Micron Technology, Inc.",
    referenceSymbol: "MU (NASDAQ)",
    venue: "Bitget · tokenized",
    decisionState: "NO ACTION",
    note: "Tariff headline judged insufficiently specific.",
  },
];

export function findInstrument(symbol: string): CatalogEntry | null {
  return instrumentCatalog.find((i) => i.symbol === symbol) ?? null;
}
