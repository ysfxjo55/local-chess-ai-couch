import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { GameDetail } from "@/lib/apiTypes";

export function useTriggerAnalysis(gameId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerAnalysis(gameId),
    onSuccess: (res) => {
      // Patch the cached GameDetail directly rather than refetching — the
      // backend call already returned the finished text, no need for a
      // second round-trip.
      queryClient.setQueryData<GameDetail>(["game", gameId], (prev) =>
        prev ? { ...prev, coach_analysis: res.coach_analysis } : prev,
      );
    },
  });
}
