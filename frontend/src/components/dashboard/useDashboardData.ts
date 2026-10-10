"use client";

import { useEffect, useState } from "react";
import type {
  ActivityRecord,
  EventBundle,
  InstrumentIdentity,
  MarketEvent,
  MarketObservation,
} from "@/types/domain";
import { dataProvider } from "@/services";
import type { CycleSnapshot } from "@/services/liveDataProvider";

export type CycleStatus = CycleSnapshot;
import { instrumentCatalog } from "@/data/instrumentCatalog";
import { useDashboardStore, CORE_SCENARIO_EVENT_IDS } from "@/lib/dashboardStore";

export interface DashboardData {
  events: MarketEvent[];
  observations: MarketObservation[];
  instruments: InstrumentIdentity[];
  activity: ActivityRecord[];
  cycle: CycleStatus | null;
  loading: boolean;
  error: string | null;
}

/** Loads the preview workspace snapshot through the data provider. */
export function useDashboardData(): DashboardData {
  const dataMode = useDashboardStore((s) => s.settings.dataMode);
  const [snapshot, setSnapshot] = useState<{
    events: MarketEvent[];
    observations: MarketObservation[];
    instruments: InstrumentIdentity[];
    activity: ActivityRecord[];
    cycle: CycleStatus | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const loader = dataProvider as { loadDashboard?: () => Promise<NonNullable<typeof snapshot>> };
    const request = loader.loadDashboard
      ? loader.loadDashboard()
      : Promise.all([
          dataProvider.listEvents(),
          dataProvider.getMarketOverview(),
          dataProvider.listInstruments(),
          dataProvider.listActivity(),
          "getCycle" in dataProvider
            ? (dataProvider as { getCycle: () => Promise<CycleStatus> }).getCycle()
            : Promise.resolve(null),
        ]).then(([events, observations, instruments, activity, cycle]) => ({
          events, observations, instruments, activity, cycle,
        }));
    request.then(({ events, observations, instruments, activity, cycle }) => {
      if (!alive) return;
      setSnapshot({ events, observations, instruments, activity, cycle });
    }).catch((err: unknown) => {
      if (!alive) return;
      setError(err instanceof Error ? err.message : "backend unavailable");
      setSnapshot({ events: [], observations: [], instruments: [], activity: [], cycle: null });
    });
    return () => {
      alive = false;
    };
  }, []);

  const coreEvents = snapshot?.events.filter((e) => CORE_SCENARIO_EVENT_IDS.has(e.id)) ?? [];
  const visibleEvents = snapshot
    ? dataMode === "core" && coreEvents.length > 0
      ? coreEvents
      : snapshot.events
    : [];

  return {
    events: visibleEvents,
    observations: snapshot?.observations ?? [],
    instruments: snapshot?.instruments ?? [],
    activity: snapshot?.activity ?? [],
    cycle: snapshot?.cycle ?? null,
    loading: snapshot === null,
    error,
  };
}

/** Loads one event bundle (decision detail panel). */
export function useEventBundle(eventId: string | null): {
  bundle: EventBundle | null;
  loading: boolean;
} {
  const [loaded, setLoaded] = useState<{ eventId: string; bundle: EventBundle | null } | null>(null);

  useEffect(() => {
    if (!eventId) return;
    let alive = true;
    dataProvider.getEventBundle(eventId).then((b) => {
      if (!alive) return;
      setLoaded({ eventId, bundle: b });
    });
    return () => {
      alive = false;
    };
  }, [eventId]);

  const current = loaded && loaded.eventId === eventId ? loaded : null;
  return { bundle: current?.bundle ?? null, loading: !!eventId && !current };
}

/** Observation lookup helper bound to loaded data. */
export function observationFor(
  observations: MarketObservation[],
  symbol: string | null
): MarketObservation | null {
  if (!symbol) return null;
  return observations.find((o) => o.symbol === symbol) ?? null;
}

/** Catalog entry lookup with fallback to plain instrument identity. */
export function instrumentFor(
  instruments: InstrumentIdentity[],
  symbol: string | null
): InstrumentIdentity | null {
  if (!symbol) return null;
  return (
    instruments.find((i) => i.symbol === symbol) ??
    instrumentCatalog.find((i) => i.symbol === symbol) ??
    null
  );
}
