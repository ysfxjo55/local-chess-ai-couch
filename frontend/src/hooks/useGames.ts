import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { SyncStatusResponse } from "@/lib/apiTypes";

export function useGamesList(limit: number, offset: number) {
  return useQuery({
    queryKey: ["games", { limit, offset }],
    queryFn: ({ signal }) => api.listGames(limit, offset, signal),
    placeholderData: (previous) => previous,
  });
}

export function useGame(id: number) {
  return useQuery({
    queryKey: ["game", id],
    queryFn: ({ signal }) => api.getGame(id, signal),
    enabled: Number.isFinite(id),
  });
}

/** Starts a durable backend sync and polls it sequentially without overlap. */
export function useSyncGames() {
  const queryClient = useQueryClient();
  const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runRef = useRef(0);
  const unmountedRef = useRef(false);

  const cancelPolling = useCallback(() => {
    runRef.current += 1;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const invalidateAfterSync = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["games"] });
    queryClient.invalidateQueries({ queryKey: ["stats"] });
    queryClient.invalidateQueries({ queryKey: ["puzzle"] });
    queryClient.invalidateQueries({ queryKey: ["learning"] });
  }, [queryClient]);

  const reset = useCallback(() => {
    cancelPolling();
    setSyncStatus(null);
    setIsPending(false);
    setError(null);
    setIsSuccess(false);
  }, [cancelPolling]);

  useEffect(() => () => {
    unmountedRef.current = true;
    cancelPolling();
  }, [cancelPolling]);

  const mutate = useCallback(async () => {
    reset();
    const runId = runRef.current;
    setIsPending(true);
    try {
      const initial = await api.syncGames();
      if (unmountedRef.current || runId !== runRef.current) return;
      setSyncStatus(initial);

      const finish = (status: SyncStatusResponse) => {
        if (status.status === "done") {
          setIsPending(false);
          setIsSuccess(true);
          invalidateAfterSync();
        } else if (status.status === "error") {
          setIsPending(false);
          setError(new ApiError(500, status.error ?? "Sync failed"));
        }
      };
      if (initial.status === "done" || initial.status === "error") {
        finish(initial);
        return;
      }

      const poll = async () => {
        if (unmountedRef.current || runId !== runRef.current) return;
        try {
          const latest = await api.syncStatus();
          if (unmountedRef.current || runId !== runRef.current) return;
          setSyncStatus(latest);
          if (latest.status === "done" || latest.status === "error") {
            finish(latest);
            return;
          }
        } catch {
          // Keep the current durable job status and retry; a short API outage
          // should not start a second import or discard the visible progress.
        }
        if (!unmountedRef.current && runId === runRef.current) timerRef.current = setTimeout(poll, 3_000);
      };
      timerRef.current = setTimeout(poll, 3_000);
    } catch (reason) {
      if (!unmountedRef.current && runId === runRef.current) {
        setIsPending(false);
        setError(reason instanceof Error ? reason : new Error("Could not start sync"));
      }
    }
  }, [invalidateAfterSync, reset]);

  return { mutate, reset, syncStatus, isPending, error, isSuccess };
}
