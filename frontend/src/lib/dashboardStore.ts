"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type DashboardTab = "overview" | "events" | "decisions" | "activity";

export interface DashboardSettings {
  /** Calm mode — disables decorative animation app-wide. */
  reduceMotion: boolean;
  /** Show full risk-check detail by default. */
  detailedRisk: boolean;
  /** Preview data mode: full feed or core scenarios only. */
  dataMode: "full" | "core";
}

interface DashboardState {
  tab: DashboardTab;
  selectedEventId: string | null;
  searchQuery: string;
  settings: DashboardSettings;
  setTab: (tab: DashboardTab) => void;
  selectEvent: (eventId: string | null) => void;
  setSearch: (q: string) => void;
  updateSettings: (patch: Partial<DashboardSettings>) => void;
}

export const CORE_SCENARIO_EVENT_IDS = new Set([
  "EV-1001",
  "EV-1002",
  "EV-1003",
  "EV-1004",
  "EV-1005",
  "EV-1006",
]);

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set) => ({
      tab: "overview",
      selectedEventId: null,
      searchQuery: "",
      settings: {
        reduceMotion: false,
        detailedRisk: false,
        dataMode: "full",
      },
      setTab: (tab) => set({ tab }),
      selectEvent: (selectedEventId) => set({ selectedEventId }),
      setSearch: (searchQuery) => set({ searchQuery }),
      updateSettings: (patch) =>
        set((s) => ({ settings: { ...s.settings, ...patch } })),
    }),
    {
      name: "aftermath-dashboard-preferences",
      partialize: (s) => ({ settings: s.settings }),
    }
  )
);
