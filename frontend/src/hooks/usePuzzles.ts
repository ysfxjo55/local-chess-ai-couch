import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PuzzleAttemptRequest, PuzzleGuessRequest } from "@/lib/apiTypes";

/**
 * `staleTime: Infinity` — the current puzzle must not silently change out
 * from under the board mid-attempt (e.g. a window refocus refetch). The
 * Puzzles page advances it explicitly via `refetch()` once the player has
 * seen the result and clicks "Next".
 */
export function useNextPuzzle(gameId?: number) {
  return useQuery({
    queryKey: ["puzzle", "next", gameId ?? "all"],
    queryFn: () => api.nextPuzzle(gameId),
    staleTime: Infinity,
  });
}

export function usePuzzleGames() {
  return useQuery({
    queryKey: ["puzzle", "games"],
    queryFn: () => api.puzzleGames(),
  });
}

export function usePuzzleStats() {
  return useQuery({
    queryKey: ["puzzle", "stats"],
    queryFn: () => api.puzzleStats(),
  });
}

export function useGuessPuzzle() {
  return useMutation({
    mutationFn: ({ gameId, ply, body }: { gameId: number; ply: number; body: PuzzleGuessRequest }) =>
      api.guessPuzzle(gameId, ply, body),
  });
}

export function useAttemptPuzzle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PuzzleAttemptRequest) => api.attemptPuzzle(body),
    onSuccess: (_res, vars) => {
      queryClient.invalidateQueries({ queryKey: ["puzzle", "stats"] });
      queryClient.invalidateQueries({ queryKey: ["puzzle", "games"] });
      // Refreshes puzzle_correct on this game's moves — drives the
      // per-game progress chips (and GameDetail's "fixed" markers).
      queryClient.invalidateQueries({ queryKey: ["game", vars.game_id] });
    },
  });
}
