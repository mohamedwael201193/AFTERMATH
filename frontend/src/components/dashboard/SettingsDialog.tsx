"use client";

import { Plug, Settings2, Sparkles, ListFilter, Database } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useDashboardStore } from "@/lib/dashboardStore";
import { cn } from "@/lib/utils";

/**
 * Minimal settings — only preferences that genuinely change behavior.
 * The API row is an honest placeholder: nothing here claims a live connection.
 */
export function SettingsDialog() {
  const settings = useDashboardStore((s) => s.settings);
  const updateSettings = useDashboardStore((s) => s.updateSettings);

  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          aria-label="Open workspace settings"
          className="inline-flex h-10 w-10 items-center justify-center rounded-full border-2 border-ink bg-warmwhite text-ink transition-colors hover:bg-forest-mist"
        >
          <Settings2 className="h-4.5 w-4.5" aria-hidden="true" />
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-lg rounded-3xl border-2 border-ink bg-warmwhite sm:rounded-[2rem]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-display text-lg uppercase tracking-tight text-forest-deep">
            Workspace settings
          </DialogTitle>
          <DialogDescription className="text-sm text-ink-soft">
            Preferences apply immediately and persist in this browser. They never
            change what the data claims to be.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 pt-2">
          {/* motion */}
          <div className="flex items-start justify-between gap-4 rounded-2xl border-2 border-line bg-paper p-4">
            <div className="flex gap-3">
              <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-forest" aria-hidden="true" />
              <div>
                <Label htmlFor="set-motion" className="text-sm font-bold text-ink">
                  Calm motion
                </Label>
                <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">
                  Pauses decorative animation — orbits, floats, marquee. Charts and
                  status changes keep working. Your OS setting is respected too.
                </p>
              </div>
            </div>
            <Switch
              id="set-motion"
              checked={settings.reduceMotion}
              onCheckedChange={(v) => updateSettings({ reduceMotion: v })}
              aria-label="Calm motion"
            />
          </div>

          {/* risk detail */}
          <div className="flex items-start justify-between gap-4 rounded-2xl border-2 border-line bg-paper p-4">
            <div className="flex gap-3">
              <ListFilter className="mt-0.5 h-5 w-5 shrink-0 text-forest" aria-hidden="true" />
              <div>
                <Label htmlFor="set-risk" className="text-sm font-bold text-ink">
                  Detailed risk explanations
                </Label>
                <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">
                  Shows the full explanation of every risk check by default,
                  including checks that passed.
                </p>
              </div>
            </div>
            <Switch
              id="set-risk"
              checked={settings.detailedRisk}
              onCheckedChange={(v) => updateSettings({ detailedRisk: v })}
              aria-label="Detailed risk explanations"
            />
          </div>

          {/* data mode */}
          <div className="rounded-2xl border-2 border-line bg-paper p-4">
            <div className="flex gap-3">
              <Database className="mt-0.5 h-5 w-5 shrink-0 text-forest" aria-hidden="true" />
              <div className="flex-1">
                <Label className="text-sm font-bold text-ink">Event filter</Label>
                <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">
                  Full feed shows every stored event. Core scenarios only narrows
                  the old sample ids, so live market rows stay visible.
                </p>
                <div
                  role="group"
                  aria-label="Preview data mode"
                  className="mt-3 inline-flex rounded-full border-2 border-ink bg-warmwhite p-0.5"
                >
                  {(
                    [
                      { value: "full", label: "Full feed" },
                      { value: "core", label: "Core scenarios" },
                    ] as const
                  ).map((m) => (
                    <button
                      key={m.value}
                      onClick={() => updateSettings({ dataMode: m.value })}
                      aria-pressed={settings.dataMode === m.value}
                      className={cn(
                        "rounded-full px-3.5 py-1.5 text-xs font-bold transition-colors",
                        settings.dataMode === m.value
                          ? "bg-forest text-paper"
                          : "text-ink-soft hover:bg-forest-mist"
                      )}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* API placeholder */}
          <div className="flex items-start justify-between gap-4 rounded-2xl border-2 border-dashed border-line-strong bg-paper p-4">
            <div className="flex gap-3">
              <Plug className="mt-0.5 h-5 w-5 shrink-0 text-ink-soft" aria-hidden="true" />
              <div>
                <p className="text-sm font-bold text-ink">API connection</p>
                <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">
                  This dashboard reads the production ledger through the same-origin
                  reader. It does not use the illustrative preview dataset. The
                  hourly paper cycle is not a continuous connection.
                </p>
              </div>
            </div>
            <span className="rounded-full border-2 border-ink bg-forest-mist px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-forest-deep">
              Production
            </span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
