import { useCallback, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SyncStatusResponse } from "@/lib/apiTypes";

export function useGamesList(limit: number, offset: number) {
  return useQuery({
    queryKey: ["games", { limit, offset }],
    queryFn: () => api.listGames(limit, offset),
    placeholderData: (prev) => prev,
  });
}

export function useGame(id: number) {
  return useQuery({
    queryKey: ["game", id],
    queryFn: () => api.getGame(id),
    enabled: Number.isFinite(id),
  });
}

/**
 * Async sync: POST /sync starts a background job, then we poll
 * GET /sync/status until it finishes. The caller sees `syncStatus`
 * (the live poll state) and can trigger a new sync via `mutate()`.
 */
export function useSyncGames() {
  const queryClient = useQueryClient();
  const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const reset = useCallback(() => {
    setSyncStatus(null);
    setIsPending(false);
    setError(null);
    setIsSuccess(false);
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const mutate = useCallback(async () => {
    reset();
    setIsPending(true);
    setError(null);

    try {
      // Start the background sync
      const initial = await api.syncGames();
      setSyncStatus(initial);

      // If it's already done (tiny sync), finish immediately
      if (initial.status === "done") {
        setIsPending(false);
        setIsSuccess(true);
        queryClient.invalidateQueries({ queryKey: ["games"] });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
        return;
      }
      if (initial.status === "error") {
        setIsPending(false);
        setError(new Error(initial.error ?? "Sync failed"));
        return;
      }

      // Poll for progress
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.syncStatus();
          setSyncStatus(status);

          if (status.status === "done") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setIsPending(false);
            setIsSuccess(true);
            queryClient.invalidateQueries({ queryKey: ["games"] });
            queryClient.invalidateQueries({ queryKey: ["stats"] });
          } else if (status.status === "error") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setIsPending(false);
            setError(new Error(status.error ?? "Sync failed"));
          }
        } catch {
          // Poll request failed — server might be restarting, keep trying
        }
      }, 3000);
    } catch (err) {
      setIsPending(false);
      setError(err instanceof Error ? err : new Error("Could not start sync"));
    }
  }, [queryClient, reset]);

  return { mutate, reset, syncStatus, isPending, error, isSuccess };
}
