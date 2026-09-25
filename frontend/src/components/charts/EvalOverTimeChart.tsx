import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  ReferenceLine,
  Tooltip,
} from "recharts";
import type { MoveOut } from "@/lib/apiTypes";

const MATE_THRESHOLD = 9500;

function clampForChart(cp: number): number {
  // Compress mate scores so one mate-in-N move doesn't flatten the whole
  // chart's scale for every other, genuinely close, position.
  return Math.max(-1000, Math.min(1000, cp));
}

interface EvalOverTimeChartProps {
  moves: MoveOut[];
  currentPly: number;
  onSelectPly: (ply: number) => void;
}

export function EvalOverTimeChart({
  moves,
  currentPly,
  onSelectPly,
}: EvalOverTimeChartProps) {
  const data = moves.map((m, ply) => ({
    ply,
    eval: clampForChart(m.eval_after),
    rawEval: m.eval_after,
  }));

  return (
    <div className="h-32 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 4, right: 4, bottom: 0, left: 4 }}
          onClick={(state) => {
            if (state && typeof state.activeLabel === "number") {
              onSelectPly(state.activeLabel);
            }
          }}
        >
          <XAxis dataKey="ply" hide />
          <YAxis domain={[-1000, 1000]} hide />
          <ReferenceLine y={0} stroke="#2f333b" />
          <ReferenceLine x={currentPly} stroke="#d4a373" strokeDasharray="3 3" />
          <Tooltip
            cursor={false}
            contentStyle={{
              background: "#1e2025",
              border: "1px solid #2f333b",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(ply) => `Ply ${Number(ply) + 1}`}
            formatter={(_value, _name, item) => {
              const raw = item.payload.rawEval as number;
              const label =
                Math.abs(raw) >= MATE_THRESHOLD
                  ? "Mate"
                  : (raw / 100).toFixed(1);
              return [label, "Eval"];
            }}
          />
          <Line
            type="monotone"
            dataKey="eval"
            stroke="#e5b869"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
