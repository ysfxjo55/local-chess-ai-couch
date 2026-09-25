import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import type { AccuracyTrendPoint } from "@/lib/apiTypes";
import { EmptyState } from "@/components/shared/EmptyState";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function AccuracyTrendChart({ data }: { data: AccuracyTrendPoint[] }) {
  if (data.length === 0) {
    return <EmptyState title="No data in this range" />;
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2f333b" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="#9a978f"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            reversed
            stroke="#9a978f"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={32}
          />
          <Tooltip
            labelFormatter={(v) => formatDate(String(v))}
            formatter={(v) => [Number(v).toFixed(0), "Avg. CP loss"]}
            contentStyle={{
              background: "#1e2025",
              border: "1px solid #2f333b",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Line
            type="monotone"
            dataKey="avg_cp_loss"
            stroke="#e5b869"
            strokeWidth={2}
            dot={{ r: 3, fill: "#e5b869" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
