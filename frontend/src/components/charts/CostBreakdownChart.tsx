"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CostEstimate } from "@/types/domain";
import { formatUsd } from "@/lib/format";

const COLORS = ["#086B32", "#C9A227", "#65695F", "#9A6106"];

/**
 * Estimated execution-cost breakdown — fees vs slippage per fill.
 * Estimates only; never presented as realized costs.
 */
export function CostBreakdownChart({
  costs,
  height = 160,
}: {
  costs: CostEstimate[];
  height?: number;
}) {
  const data = costs.map((c) => ({ name: c.label, usd: c.usd }));
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="name"
            stroke="#65695F"
            tick={{ fontSize: 11, fontWeight: 600 }}
            tickLine={false}
            axisLine={{ stroke: "#B9B9A6", strokeWidth: 2 }}
          />
          <YAxis hide domain={[0, "dataMax + 0.1"]} />
          <Tooltip
            cursor={{ fill: "#E3ECDF", radius: 8 }}
            formatter={(v: number) => [formatUsd(v), "Estimated cost"]}
            contentStyle={{
              background: "#FFFEF8",
              border: "2px solid #171916",
              borderRadius: 12,
              boxShadow: "0 3px 0 rgba(23,25,22,0.85)",
              fontSize: 12,
              fontWeight: 600,
            }}
          />
          <Bar dataKey="usd" radius={[7, 7, 0, 0]} maxBarSize={46}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="#171916" strokeWidth={1.6} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
