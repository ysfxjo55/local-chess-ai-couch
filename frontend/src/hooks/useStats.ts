import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { StatsRange } from "@/lib/apiTypes";

export function useStatsOverview(range: StatsRange) {
  return useQuery({
    queryKey: ["stats", range],
    queryFn: () => api.statsOverview(range),
  });
}

export function useRepertoire(range: StatsRange, minGames = 3) {
  return useQuery({
    queryKey: ["stats", "repertoire", range, minGames],
    queryFn: () => api.repertoire(range, minGames),
  });
}
