export const dynamic = "force-dynamic";

const BASE = process.env.AFTERMATH_API_BASE || "https://aftermath-api.onrender.com";

type Tally = { rows: number; closed: number; open: number; cycles: number; readable: boolean };

async function load(): Promise<Tally> {
  try {
    const [trades, cycles] = await Promise.all([
      fetch(BASE + "/paper-trading-log.csv", { cache: "no-store" }),
      fetch(BASE + "/paper-cycle-log.csv", { cache: "no-store" }),
    ]);
    if (!trades.ok || !cycles.ok) return { rows: 0, closed: 0, open: 0, cycles: 0, readable: false };
    const tradeText = await trades.text();
    const cycleText = await cycles.text();
    const tally = tallyTrades(tradeText);
    return { ...tally, cycles: dataLines(cycleText), readable: true };
  } catch {
    return { rows: 0, closed: 0, open: 0, cycles: 0, readable: false };
  }
}

function dataLines(csv: string): number {
  return csv.trim().split(/\n/).filter((line) => line.trim()).length - 1;
}

function tallyTrades(csv: string): { rows: number; closed: number; open: number } {
  const lines = csv.trim().split(/\n/).filter((line) => line.trim());
  if (lines.length === 0) return { rows: 0, closed: 0, open: 0 };
  const status = lines[0].split(",").indexOf("trade_status");
  let closed = 0;
  let open = 0;
  for (const line of lines.slice(1)) {
    const cell = line.split(",")[status];
    if (cell === "CLOSED") closed += 1;
    if (cell === "OPEN") open += 1;
  }
  return { rows: Math.max(lines.length - 1, 0), closed, open };
}

export default async function PaperTradingLogPage() {
  const tally = await load();
  return (
    <main className="mx-auto min-h-screen max-w-3xl bg-paper px-6 py-12 text-ink">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">AFTERMATH · Track 2</p>
      <h1 className="mt-3 font-serif text-4xl text-forest">Paper trading log</h1>
      <p className="mt-4 text-base leading-relaxed">
        This is a public read-only view of the prospective ledger. It does not accept orders and it does not include
        historical replay, fixtures, backtests, or GetAgent Studio runs.
      </p>
      {tally.readable ? (
        <p className="mt-4 text-base leading-relaxed">
          {tally.closed === 0
            ? "No forward paper trade has closed. A row appears only after a real Item 2.02 filing is accepted, the model decides, the risk governor approves, and the paper position is entered and closed on later books with measured fees and funding. That filing has not produced a closed trade. Open rows are not outcomes. An empty cost cell is a missing measurement, not a zero."
            : `${tally.closed} closed forward paper trades are recorded. They are paper results, not a profitability claim.`}
        </p>
      ) : (
        <p className="mt-4 text-base leading-relaxed">The ledger export could not be read. No trade count is shown in its place.</p>
      )}
      <ul className="mt-6 space-y-2 text-base">
        <li>
          <a className="font-semibold text-forest underline" href="/paper-trading-log.csv">Trade log</a>
          {tally.readable ? ` — ${tally.rows} forward rows, ${tally.closed} closed, ${tally.open} open.` : ""}
        </li>
        <li>
          <a className="font-semibold text-forest underline" href="/paper-cycle-log.csv">Cycle log</a>
          {tally.readable ? ` — ${tally.cycles} no-trade or refusal cycles. These are not fills.` : ""}
        </li>
      </ul>
      <p className="mt-6 text-sm leading-relaxed text-ink-soft">
        The venue is internal_paper or bitget_demo. The registered strategy is S-A and is unchanged. A positive funding
        rate is a cost for a long and a credit for a short. The paper account starts at 10000 USDT. A balance change is
        the closed net P&amp;L only.
      </p>
      <p className="mt-8 text-sm">
        <a className="font-semibold text-forest underline" href="/">Back to the site</a>
      </p>
    </main>
  );
}
