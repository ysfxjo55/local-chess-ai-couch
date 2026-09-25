import { useState } from "react";
import { StatsBar } from "@/components/dashboard/StatsBar";
import { LessonsCard } from "@/components/dashboard/LessonsCard";
import { SyncDrawer } from "@/components/dashboard/SyncDrawer";
import { GamesTable } from "@/components/dashboard/GamesTable";
import { Pagination } from "@/components/dashboard/Pagination";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Skeleton } from "@/components/ui/skeleton";
import { useGamesList } from "@/hooks/useGames";
import { useStatsOverview } from "@/hooks/useStats";
import { ApiError } from "@/lib/api";

const PAGE_SIZE = 10;

export default function Dashboard() {
  const [page, setPage] = useState(0);
  const games = useGamesList(PAGE_SIZE, page * PAGE_SIZE);
  const stats = useStatsOverview("all");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-ink">Dashboard</h1>
          <p className="text-sm text-ink-muted">Your recent games at a glance</p>
        </div>
        <SyncDrawer />
      </div>

      <StatsBar
        stats={stats.data}
        totalGames={games.data?.total}
        isLoading={stats.isLoading}
      />

      <LessonsCard />

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-ink-muted">Recent games</h2>

        {games.isLoading && (
          <div className="space-y-1.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-[52px] rounded-lg" />
            ))}
          </div>
        )}

        {games.isError && (
          <ErrorBanner
            message={
              games.error instanceof ApiError
                ? games.error.message
                : "Could not load games."
            }
            onRetry={() => games.refetch()}
          />
        )}

        {games.data && (
          <>
            <GamesTable games={games.data.games} />
            {games.data.total > PAGE_SIZE && (
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={games.data.total}
                onPageChange={setPage}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
