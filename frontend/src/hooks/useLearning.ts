import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useDailyPlan() {
  return useQuery({ queryKey: ["learning", "daily-plan"], queryFn: ({ signal }) => api.dailyPlan(signal), staleTime: 5 * 60_000 });
}

export function usePlayerProfile() {
  return useQuery({ queryKey: ["learning", "profile"], queryFn: ({ signal }) => api.playerProfile(signal), staleTime: 60_000 });
}

export function useCompletePlanItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.completePlanItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["learning", "daily-plan"] }),
  });
}
