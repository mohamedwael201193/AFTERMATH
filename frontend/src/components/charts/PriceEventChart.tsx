"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PriceSeries } from "@/types/domain";
import { formatEt } from "@/lib/format";
import { cn } from "@/lib/utils";

export type ChartRange = "all" | "session" | "afterHours";

const RANGE_LABELS: Record<ChartRange, string> = {
  all: "Full day",
  session: "Cash session",
  afterHours: "After hours",
};

function inRange(iso: string, range: ChartRange): boolean {
  if (range === "all") return true;
  const t = Date.parse(iso);
  const open = Date.parse("2026-01-09T14:30:00Z");
  const close = Date.parse("2026-01-09T21:00:00Z");
  if (range === "session") return t >= open && t <= close;
  return t < open || t > close;
}

interface TooltipPayloadItem {
  active?: boolean;
  payload?: Array<{ payload: { t: string; p: number; label?: string } }>;
}

function ChartTooltip({ active, payload }: TooltipPayloadItem) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl border-2 border-ink bg-warmwhite px-3 py-2 shadow-[0_3px_0_rgba(23,25,22,0.85)]">
      <p className="tnum text-xs font-bold text-ink">{d.label ?? formatEt(d.t, "full")} ET</p>
      <p className="tnum text-sm font-bold text-forest">
        {d.p.toFixed(2)} USD
      </p>
      {d.label && (
        <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-soft">
          {formatEt(d.t, "full")} ET
        </p>
      )}
    </div>
  );
}

/**
 * Price movement with event markers — the dashboard's main chart.
 * Deterministic preview data; markers show events and session boundaries.
 */
export function PriceEventChart({
  series,
  range = "all",
  className,
  compact = false,
}: {
  series: PriceSeries;
  range?: ChartRange;
  className?: string;
  compact?: boolean;
}) {
  const data = useMemo(() => {
    const points = series.points.filter((p) => inRange(p.t, range));
    const markers = series.markers
      .filter((m) => inRange(m.t, range))
      .map((m) => {
        // attach marker label to nearest point for tooltip display
        const nearest = points.reduce((acc, p) =>
          Math.abs(Date.parse(p.t) - Date.parse(m.t)) <
          Math.abs(Date.parse(acc.t) - Date.parse(m.t))
            ? p
            : acc
        );
        return { t: nearest.t, p: nearest.p, label: m.label, kind: m.kind };
      });
    return { points, markers };
  }, [series, range]);

  const merged = useMemo(() => {
    const markerTs = new Set(data.markers.map((m) => m.t));
    return [
      ...data.points.filter((p) => !markerTs.has(p.t)),
      ...data.markers,
    ].sort((a, b) => Date.parse(a.t) - Date.parse(b.t));
  }, [data]);

  const yDomain = useMemo<[number, number]>(() => {
    const values = merged.map((p) => p.p);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.15 || 1;
    return [Number((min - pad).toFixed(2)), Number((max + pad).toFixed(2))];
  }, [merged]);

  return (
    <div className={cn("w-full", className)}>
      <ResponsiveContainer width="100%" height={compact ? 180 : 280}>
        <LineChart data={merged} margin={{ top: 12, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="#D8D8CA" strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="t"
            tickFormatter={(t: string) => formatEt(t)}
            stroke="#65695F"
            tick={{ fontSize: 11, fontWeight: 600 }}
            tickLine={false}
            axisLine={{ stroke: "#B9B9A6", strokeWidth: 2 }}
            minTickGap={44}
          />
          <YAxis
            domain={yDomain}
            stroke="#65695F"
            tick={{ fontSize: 11, fontWeight: 600 }}
            tickLine={false}
            axisLine={false}
            width={54}
            tickFormatter={(v: number) => v.toFixed(0)}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: "#B9B9A6", strokeWidth: 1.5 }} />
          <Line
            type="monotone"
            dataKey="p"
            stroke="#086B32"
            strokeWidth={3}
            dot={false}
            activeDot={{ r: 5, fill: "#086B32", stroke: "#171916", strokeWidth: 2 }}
            isAnimationActive
            animationDuration={700}
          />
          {data.markers.map((m) => (
            <ReferenceDot
              key={m.t + "-" + m.label}
              x={m.t}
              y={m.p}
              r={5}
              fill={m.kind === "EVENT" ? "#C9A227" : "#FFFEF8"}
              stroke="#171916"
              strokeWidth={2}
              ifOverflow="extendDomain"
            />
          ))}
          {data.markers
            .filter((m) => m.kind === "SESSION")
            .map((m) => (
              <ReferenceLine
                key={m.t + "-line"}
                x={m.t}
                stroke="#B9B9A6"
                strokeDasharray="4 5"
                strokeWidth={1.5}
              />
            ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Range toggle used above the chart. */
export function ChartRangeToggle({
  range,
  onChange,
}: {
  range: ChartRange;
  onChange: (r: ChartRange) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Chart time range"
      className="inline-flex rounded-full border-2 border-ink bg-paper p-0.5"
    >
      {(Object.keys(RANGE_LABELS) as ChartRange[]).map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          aria-pressed={range === r}
          className={cn(
            "rounded-full px-3 py-1 text-[11px] font-bold transition-colors",
            range === r ? "bg-forest text-paper" : "text-ink-soft hover:bg-forest-mist"
          )}
        >
          {RANGE_LABELS[r]}
        </button>
      ))}
    </div>
  );
}
