"use client";

import { useEffect } from "react";
import {
  LayoutDashboard,
  Zap,
  Gavel,
  ReceiptText,
  ArrowLeft,
  X,
  MoonStar,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { AftermathWordmark } from "@/components/artwork/AftermathMark";
import { SettingsDialog } from "@/components/dashboard/SettingsDialog";
import { OverviewPanel } from "@/components/dashboard/OverviewPanel";
import { EventFeed } from "@/components/dashboard/EventFeed";
import { HistoryPanel } from "@/components/dashboard/HistoryPanel";
import { ActivityPanel } from "@/components/dashboard/ActivityPanel";
import { DecisionDetail } from "@/components/dashboard/DecisionDetail";
import { useDashboardData, useEventBundle } from "@/components/dashboard/useDashboardData";
import { useDashboardStore, type DashboardTab } from "@/lib/dashboardStore";
import { useBelowXl } from "@/hooks/use-below-xl";
import { cn } from "@/lib/utils";

const NAV: Array<{ id: DashboardTab; label: string; icon: React.ElementType; hint: string }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, hint: "The whole picture" },
  { id: "events", label: "Events", icon: Zap, hint: "What's happening" },
  { id: "decisions", label: "Decisions", icon: Gavel, hint: "History & filters" },
  { id: "activity", label: "Activity", icon: ReceiptText, hint: "Paper ledger" },
];

function MarketStatusChips({ cycle }: { cycle: ReturnType<typeof useDashboardData>["cycle"] }) {
  const scheduler = cycle?.scheduler ?? "unknown";
  const schedule = cycle?.schedule ?? null;
  const sec = cycle?.secEdgarStatus ?? "unknown";
  const modelCalls = cycle?.modelCallsLatest;
  const kill = cycle?.killSwitch === true;

  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] font-bold">
      <span className="inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-warn-soft px-2.5 py-1 text-warn">
        <MoonStar className="h-3.5 w-3.5" aria-hidden="true" />
        Bitget public market
        <span className="hidden font-semibold text-ink-soft sm:inline">
          · USDT perpetuals
        </span>
      </span>
      <span className="inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-forest-mist px-2.5 py-1 text-forest-deep">
        <span className="relative flex h-2 w-2" aria-hidden="true">
          <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-forest" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-forest" />
        </span>
        {cycle?.continuousOperation ? "Continuous" : "Hourly cycle · not continuous"}
        {schedule ? (
          <span className="hidden font-semibold text-ink-soft sm:inline">· {schedule}</span>
        ) : null}
      </span>
      <span className="rounded-full border border-line-strong bg-paper px-2.5 py-1 font-semibold text-ink-soft">
        Scheduler · {scheduler}
      </span>
      <span className="rounded-full border border-line-strong bg-paper px-2.5 py-1 font-semibold text-ink-soft">
        SEC · {sec}
      </span>
      <span className="rounded-full border border-line-strong bg-paper px-2.5 py-1 font-semibold text-ink-soft">
        Last cycle model calls · {modelCalls == null ? "n/a" : modelCalls}
      </span>
      <span
        className={cn(
          "rounded-full border-2 px-2.5 py-1 font-bold uppercase tracking-wide",
          kill ? "border-ink bg-risk-soft text-risk" : "border-forest bg-forest-mist text-forest-deep"
        )}
      >
        Kill switch · {kill ? "on" : "off"}
      </span>
      <span className="hidden rounded-full border border-line-strong bg-paper px-2.5 py-1 font-semibold text-ink-soft md:inline">
        Production API · paper only
      </span>
    </div>
  );
}

function SidebarNav({
  onExit,
  cycle,
}: {
  onExit: () => void;
  cycle: ReturnType<typeof useDashboardData>["cycle"];
}) {
  const tab = useDashboardStore((s) => s.tab);
  const setTab = useDashboardStore((s) => s.setTab);

  return (
    <>
      <div className="flex items-center justify-between px-5 pt-5">
        <AftermathWordmark />
      </div>
      <p className="px-5 pt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-ink-soft">
        Production ledger
      </p>

      <nav aria-label="Application sections" className="mt-6 grid gap-2 px-3">
        {NAV.map((n) => {
          const active = tab === n.id;
          return (
            <button
              key={n.id}
              onClick={() => setTab(n.id)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-[3.5rem] items-center gap-3 rounded-2xl border-2 px-3.5 py-2.5 text-left transition-all",
                active
                  ? "border-ink bg-forest text-paper shadow-[0_3px_0_rgba(23,25,22,0.85)]"
                  : "border-transparent text-ink shadow-[0_3px_0_rgba(23,25,22,0)] hover:border-line hover:bg-warmwhite"
              )}
            >
              <n.icon
                className={cn("h-5 w-5 shrink-0", active ? "text-paper" : "text-forest")}
                aria-hidden="true"
              />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-bold leading-tight">{n.label}</span>
                <span className={cn("block text-[11px] leading-tight", active ? "text-paper/75" : "text-ink-soft")}>
                  {n.hint}
                </span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="mt-auto grid gap-3 px-5 pb-5">
        <MarketStatusChips cycle={cycle} />
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={onExit}
            className="h-9 gap-1.5 rounded-full border-2 border-ink bg-warmwhite px-3.5 text-xs font-bold text-ink hover:bg-forest-mist"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            Back to site
          </Button>
          <SettingsDialog />
        </div>
      </div>
    </>
  );
}

/** Skeleton state while the preview workspace snapshot loads. */
function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-6" aria-label="Loading the preview workspace" role="status">
      <div className="grid grid-cols-1 gap-4 @min-[28rem]:grid-cols-2 @min-[60rem]:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-[10.5rem] animate-pulse rounded-3xl border-2 border-line bg-paper"
            style={{ animationDelay: `${i * 120}ms` }}
          />
        ))}
      </div>
      <div className="h-[22rem] animate-pulse rounded-3xl border-2 border-line bg-paper" />
      <div className="grid grid-cols-1 gap-3 @min-[28rem]:grid-cols-2 @min-[60rem]:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-3xl border-2 border-line bg-paper"
            style={{ animationDelay: `${i * 90}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

/** The decision detail panel content with its close control. */
function DetailPanelContent({ onClose }: { onClose: () => void }) {
  const selectedEventId = useDashboardStore((s) => s.selectedEventId);
  const { bundle, loading } = useEventBundle(selectedEventId);

  if (!selectedEventId) return null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-3 border-b-2 border-line bg-paper px-5 py-3.5">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-soft">
          {bundle
            ? bundle.observation && !bundle.event.id.startsWith("dec_")
              ? "Observation Details"
              : "Decision record"
            : selectedEventId.startsWith("dec_")
              ? "Decision record"
              : "Observation Details"}
        </p>
        <button
          onClick={onClose}
          aria-label="Close decision record"
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-warmwhite text-ink transition-colors hover:bg-risk-soft"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-6 scroll-slim">
        {loading || !bundle ? (
          <div className="grid h-full place-items-center gap-3 text-center">
            <span className="h-8 w-8 animate-spin rounded-full border-[3px] border-line-strong border-t-forest" aria-hidden="true" />
            <p className="text-sm font-semibold text-ink-soft">
              Loading the decision record…
            </p>
          </div>
        ) : (
          <DecisionDetail bundle={bundle} />
        )}
      </div>
    </div>
  );
}

export function DashboardShell({ onExit }: { onExit: () => void }) {
  const tab = useDashboardStore((s) => s.tab);
  const setTab = useDashboardStore((s) => s.setTab);
  const search = useDashboardStore((s) => s.searchQuery);
  const setSearch = useDashboardStore((s) => s.setSearch);
  const selectedEventId = useDashboardStore((s) => s.selectedEventId);
  const selectEvent = useDashboardStore((s) => s.selectEvent);
  const reduceMotion = useDashboardStore((s) => s.settings.reduceMotion);
  const { events, observations, activity, cycle, loading, error } = useDashboardData();
  const belowXl = useBelowXl();

  // Apply the calm-motion preference at the shell root.
  useEffect(() => {
    document.documentElement.classList.toggle("motion-off", reduceMotion);
    return () => document.documentElement.classList.remove("motion-off");
  }, [reduceMotion]);

  const closePanel = () => selectEvent(null);

  return (
    <div className="flex min-h-[calc(100vh-1rem)] flex-col lg:min-h-0 lg:flex-row lg:items-stretch">
      {/* desktop sidebar */}
      <aside className="sticky top-0 hidden h-auto w-[248px] shrink-0 flex-col border-r-2 border-line bg-paper lg:flex">
        <SidebarNav onExit={onExit} cycle={cycle} />
      </aside>

      {/* main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* header */}
        <header className="sticky top-0 z-30 border-b-2 border-line bg-warmwhite/95 px-4 py-3 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={onExit}
              aria-label="Back to the AFTERMATH site"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-paper text-ink transition-colors hover:bg-forest-mist lg:hidden"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            </button>
            <div className="relative order-3 min-w-0 flex-1 lg:order-none lg:max-w-xs">
              <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" aria-hidden="true" />
              <label htmlFor="dash-search" className="sr-only">
                Search events and instruments
              </label>
              <input
                id="dash-search"
                type="search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  if (e.target.value && tab === "overview") setTab("events");
                }}
                placeholder="Search events, symbols…"
                className="h-9 w-full rounded-full border-2 border-ink bg-paper pl-10 pr-4 text-sm font-semibold text-ink placeholder:text-ink-soft/70 focus-visible:outline-forest"
              />
            </div>
            <div className="hidden min-w-0 lg:block">
              <MarketStatusChips cycle={cycle} />
            </div>
            <div className="ml-auto shrink-0 lg:hidden">
              <SettingsDialog />
            </div>
          </div>
          <div className="mt-2.5 lg:hidden">
            <MarketStatusChips cycle={cycle} />
          </div>
        </header>

        {/* body: tab content + detail panel */}
        <div className="flex min-h-0 flex-1 flex-col xl:flex-row">
          <main
            id="dashboard-main"
            className="@container min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8"
            aria-live="polite"
          >
            {loading ? (
              <DashboardSkeleton />
            ) : error ? (
              <p className="rounded-md border-2 border-ink bg-risk-soft px-4 py-3 text-sm font-semibold text-risk" role="alert">
                Backend unavailable ({error}). No sample data is being shown in its place.
              </p>
            ) : (
              <>
                {tab === "overview" && (
                  <div className="grid grid-cols-1 gap-6">
                    <div>
                      <h1 className="font-display text-2xl uppercase tracking-tight text-forest-deep sm:text-3xl">
                        Overview
                      </h1>
                      <p className="mt-1 text-sm text-ink-soft">
                        What matters right now — events, decisions, risk warnings, and
                        the paper book.
                      </p>
                    </div>
                    <OverviewPanel events={events} observations={observations} activity={activity} cycle={cycle} />
                  </div>
                )}
                {tab === "events" && (
                  <div className="grid grid-cols-1 gap-6">
                    <div>
                      <h1 className="font-display text-2xl uppercase tracking-tight text-forest-deep sm:text-3xl">
                        Event feed
                      </h1>
                      <p className="mt-1 text-sm text-ink-soft">
                        Stored books and filings — each row is one persisted record.
                        Select one to open its evidence.
                      </p>
                    </div>
                    <EventFeed events={events} storedCount={cycle?.eventCount} />
                  </div>
                )}
                {tab === "decisions" && (
                  <div className="grid grid-cols-1 gap-6">
                    <div>
                      <h1 className="font-display text-2xl uppercase tracking-tight text-forest-deep sm:text-3xl">
                        Decisions
                      </h1>
                      <p className="mt-1 text-sm text-ink-soft">
                        Every recorded judgment with its risk outcome and receipt.
                        Select a row to reopen the full record.
                      </p>
                    </div>
                    <HistoryPanel activity={activity} />
                  </div>
                )}
                {tab === "activity" && (
                  <div className="grid grid-cols-1 gap-6">
                    <div>
                      <h1 className="font-display text-2xl uppercase tracking-tight text-forest-deep sm:text-3xl">
                        Activity
                      </h1>
                      <p className="mt-1 text-sm text-ink-soft">
                        The paper ledger — fills, refusals, and waits with estimated
                        costs.
                      </p>
                    </div>
                    <ActivityPanel activity={activity} />
                  </div>
                )}
              </>
            )}

            {/* empty selection helper (desktop, no event chosen) */}
            {!loading && !selectedEventId && tab !== "overview" && (
              <div className="mt-6 hidden justify-center xl:flex">
                <p className="flex items-center gap-2 rounded-full border-2 border-dashed border-line-strong bg-paper px-4 py-2 text-xs font-bold text-ink-soft">
                  Select any event or row to open its decision record →
                </p>
              </div>
            )}
          </main>

          {/* desktop detail panel — only exists while a record is selected,
              so the workspace keeps its full width for tables and charts */}
          {selectedEventId && (
            <aside
              aria-label="Decision detail"
              className="hidden w-[440px] shrink-0 border-l-2 border-line bg-warmwhite xl:block 2xl:w-[500px]"
            >
              <div className="sticky top-[4.75rem] h-[calc(100vh-6.25rem)]">
                <DetailPanelContent onClose={closePanel} />
              </div>
            </aside>
          )}
        </div>

        {/* mobile bottom tab bar */}
        <nav
          aria-label="Application sections"
          className="sticky bottom-0 z-30 mt-auto border-t-2 border-ink bg-forest-deep px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 lg:hidden"
        >
          <ul className="grid grid-cols-4 gap-1">
            {NAV.map((n) => {
              const active = tab === n.id;
              return (
                <li key={n.id}>
                  <button
                    onClick={() => setTab(n.id)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "grid w-full place-items-center gap-1 rounded-2xl px-2 py-2 transition-colors",
                      active ? "bg-paper text-forest-deep" : "text-paper/80 hover:bg-paper/10"
                    )}
                  >
                    <n.icon className="h-5 w-5" aria-hidden="true" />
                    <span className="text-[11px] font-bold leading-none">{n.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      {/* mobile / tablet detail drawer (below xl only) */}
      {belowXl && (
        <Sheet open={!!selectedEventId} onOpenChange={(o) => !o && closePanel()}>
          <SheetContent
            side="right"
            aria-describedby={undefined}
            className="w-full border-l-2 border-ink bg-warmwhite p-0 sm:max-w-md xl:hidden [&>button]:hidden"
          >
            <SheetHeader className="sr-only">
              <SheetTitle>
              {selectedEventId?.startsWith("dec_") ? "Decision record" : "Observation Details"}
            </SheetTitle>
            </SheetHeader>
            <DetailPanelContent onClose={closePanel} />
          </SheetContent>
        </Sheet>
      )}
    </div>
  );
}
