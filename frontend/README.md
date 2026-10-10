# AFTERMATH — Evidence-Governed Trading Intelligence

A premium, art-directed frontend for **AFTERMATH**: a system that connects market
events, verifiable evidence, AI reasoning, deterministic risk controls, and
auditable paper execution into one transparent workflow for tokenized US stocks
and related perpetual markets.

> **Preview workspace · illustrative data.** Every event, price, decision, and
> receipt in this build is deterministic sample data. Nothing claims to be live
> trading, verified performance, or investment advice.

---

## Run it

```bash
bun install
bun run dev        # dev server on http://localhost:3000
bun run lint       # ESLint
```

The experience lives on a single route (`/`):

- **Landing** — the product story (hero, marquee, problem timeline, workflow,
  differentiators, interactive preview, trust section, CTA).
- **Dashboard** — the product itself (Overview, Events, Decisions, Activity,
  settings). The view switch happens in the header/CTA; no navigation required.

## The visual system

| Token      | Value     | Use                                            |
| ---------- | --------- | ---------------------------------------------- |
| Forest     | `#086B32` | Primary brand green, PROCEED states            |
| Deep forest| `#064D27` | Outer frame, sidebar accents, dark panels      |
| Paper      | `#F5F2E7` | Card background, paper grain texture           |
| Warm white | `#FFFEF8` | Content surfaces                               |
| Ink        | `#171916` | Text, outlines, sticker shadows                |
| Muted ink  | `#65695F` | Secondary text, WAIT states                    |
| Line       | `#D8D8CA` | Borders                                        |
| Amber      | `#9A6106` | Warnings, REDUCE states                        |
| Risk red   | `#B3261E` | Critical risk, REJECT states                   |
| Gold       | `#C9A227` | Event markers, sparks, index-token accents     |

**Type**: Archivo Black (display) · DM Sans (interface) · Instrument Serif
(editorial asides, always in parentheses).

**Original artwork** (generated for AFTERMATH, then chroma-keyed to transparency
via `scripts/process-artwork.ts` and optimized via `scripts/optimize-artwork.ts`):

- `public/artwork/sentinel-hero.keyed.png` — the Evidence Sentinel (hero)
- `public/artwork/risk-guardian.keyed.png` — deterministic risk controls
- `public/artwork/receipt-seal.keyed.png` — auditable receipts
- `public/artwork/evidence-flow.keyed.png` — evidence into decisions
- `public/artwork/after-hours.keyed.png` — the after-hours problem
- `public/artwork/empty-search.keyed.png` — empty states

**Original SVG family** in `src/components/artwork/`: brand marks, the token
chip system (11 instruments), six workflow glyphs, decision/risk status glyphs,
decorative doodles (starbursts, squiggles, hand arrows, orbit badge), and the
empty-state character.

### Ticker & stock icons (CDN, with graceful fallback)

Dashboard data surfaces render **real exchange logos** through
`src/components/artwork/TickerIcon.tsx`. Tickers are always uppercased, and the
source chain degrades gracefully:

1. **Transparent PNG CDN (no key)** —
   `https://financialmodelingprep.com/image-stock/{TICKER}.png`
   (verified for every catalog instrument).
2. **Company-domain favicon** —
   `https://www.google.com/s2/favicons?domain={domain}&sz=64`
   (ticker→domain map inside the component).
3. **Local fallback tile** — the first two letters of the ticker in the
   original AFTERMATH chip style; broken URLs are cached module-side so they
   are never re-requested.

> Integration notes: the jsDelivr GH path for the `nvstly/icons` Nasdaq set
> (404s at the time of writing) and the `logo.dev` ticker API (requires a
> token — we don't hardcode keys) are reserved slots in `tickerIconSources`;
> prepend them there once a valid path/credential exists. The landing-page
> orbit chips intentionally keep the original SVG brand system.

## Architecture

```
src/
  app/                    route + layout + global tokens
  components/
    landing/              LandingNav, Hero, Marquee, ProblemSection,
                          HowItWorks, Differentiators, ProductPreview,
                          TrustSection, ClosingCta/Footer, LandingPage
    dashboard/            DashboardShell (frame + tabs + detail panel),
                          OverviewPanel, EventFeed, TokenExplorer,
                          HistoryPanel, ActivityPanel, SettingsDialog,
                          DecisionBadge, useDashboardData
    charts/               PriceEventChart (event markers + ranges),
                          CostBreakdownChart
    evidence/             EvidenceCard
    receipts/             ReceiptCard
    artwork/              SVG family + raster asset registry
  data/                   instrumentCatalog, eventFeedData, evidenceRecords,
                          decisionRecords, marketOverviewData, sources
  services/               marketDataProvider (interfaces),
                          previewDataProvider (implementation), wiring
  types/                  domain.ts — the complete data boundary
  lib/                    format.ts (labels + formatters),
                          dashboardStore.ts (zustand + persisted settings)
scripts/                  artwork generation + keying + optimization
screenshots/              browser-verified captures
```

## Data boundary — connecting a real backend

The UI never reads sample data directly. Everything flows through three
interfaces in `src/services/marketDataProvider.ts`:

```ts
MarketDataProvider        // instruments, overview, price series, events
DecisionService           // event bundles, activity history
ReceiptVerificationService// receipts + verification explanations
```

The deterministic preview implementation lives in
`src/services/previewDataProvider.ts`. To integrate a real backend:

1. Implement the three interfaces against your API (same shapes as
   `src/types/domain.ts` — instruments, observations, events, evidence,
   decisions, risk results, executions, receipts).
2. Change the single binding in `src/services/index.ts`:
   `import { realProvider } from "@/services/realProvider"`.
3. Surface real connection state in the **Settings → API connection** card
   (already a placeholder that honestly reads "Not connected").

Type rules the UI relies on: receipts distinguish `UNVERIFIED_PREVIEW` from
`STRUCTURE_VERIFIED`; observations carry timestamps and freshness; decision
states are exactly `PROCEED | REDUCE | WAIT | REJECT | NO ACTION`.

## Interaction inventory (all verified in-browser)

**Landing** — nav links with scroll-spy; mobile menu sheet; hero CTAs;
seamless marquee (pauses on hover/focus); scroll-revealed sections;
stepper + Play/Pause in the product preview; dashboard CTA everywhere.

**Dashboard** — tab navigation (sidebar desktop, bottom bar mobile);
event selection → decision record (right panel ≥xl, drawer below);
evidence cards expand/collapse; risk-check detail (simple/detailed setting);
chart symbol switch + range toggle with tooltips; token explorer search +
focus + inspect; decision-history filters (outcome, date, source, receipt)
with live counts + clear; activity ledger rows → full records; receipt digest
copy with toast; settings (calm motion, detailed risk, data mode) persisted
in localStorage; search across events/instruments; back-to-site with scroll
restore.

**Accessibility** — semantic landmarks, keyboard-navigable rows (Enter/Space),
visible focus rings, `aria-live` regions for tab/filter changes, labeled
meters, screen-reader text for marquee, reduced-motion support via
`prefers-reduced-motion` **and** an in-app Calm motion setting, no color-only
status (every state carries a label), tabular numerals for all figures.

## Preview scenarios

| Event      | Instrument | Scenario                                        | Outcome                    |
| ---------- | ---------- | ----------------------------------------------- | -------------------------- |
| `EV-1001`  | NVDA       | Complete evidence, primary filing               | PROCEED → paper fill       |
| `EV-1002`  | TSLA       | Missing evidence (single unverified source)     | REJECT (refusal)           |
| `EV-1003`  | META       | Misleading headline vs primary record           | REJECT (adversarial block) |
| `EV-1004`  | COIN       | Stale reference after a price gap               | WAIT (stale-data refusal)  |
| `EV-1005`  | AMZN       | Thin order book after a real filing             | REDUCE (35 % size)         |
| `EV-1006`  | AAPL       | Routine dividend, receipt structure verified    | NO ACTION                  |
| `EV-1007`  | MU         | Unspecified macro headline                      | NO ACTION                  |
| `EV-1008`  | QQQ        | Macro print, cash reference closed              | WAIT                       |

All timestamps are internally coherent around the fixed workspace clock
`2026-01-09T22:10:00Z` (Friday, US cash market closed) and render in US
Eastern time.

## Artwork pipeline

```bash
z-ai image …                         # generate on flat isolation background
bun scripts/process-artwork.ts       # corner-sampled flood-fill chroma key
bun scripts/optimize-artwork.ts      # alpha-bbox trim, resize, palette PNG
```

## Notes

- Stack: Next.js 16 (App Router) · TypeScript · Tailwind CSS 4 · shadcn/ui ·
  Framer Motion · Recharts · Zustand · Lucide (UI icons only — brand artwork
  is original SVG/PNG).
- The brief requested Vite; this environment standardizes on Next.js with a
  single `/` route, so the landing↔dashboard switch is a client view state —
  the component/data architecture remains provider-first and portable.
- Verified in a real browser at desktop (1440 px) and mobile (390 px):
  rendering, interactions, filters, charts, drawers, toasts, and zero
  horizontal overflow. See `screenshots/`.
