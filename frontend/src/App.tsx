import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { RequireAuth } from "@/lib/auth";
import { AppShell } from "@/components/layout/AppShell";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";

// Route-level code splitting for the heavier pages (Chessground/chess.js,
// Recharts, react-markdown) — keeps the initial bundle lean, which matters
// more here than on a typical app since Tailscale phone access is a
// primary use case, not just a desktop convenience.
const GameDetail = lazy(() => import("@/pages/GameDetail"));
const Insights = lazy(() => import("@/pages/Insights"));
const CoachChat = lazy(() => import("@/pages/CoachChat"));
const Puzzles = lazy(() => import("@/pages/Puzzles"));
const Sparring = lazy(() => import("@/pages/Sparring"));
const NotFound = lazy(() => import("@/pages/NotFound"));

function PageFallback() {
  return (
    <div className="flex justify-center py-24">
      <LoadingSpinner className="size-6" />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/games/:id" element={<GameDetail />} />
          <Route path="/stats" element={<Insights />} />
          <Route path="/coach" element={<CoachChat />} />
          <Route path="/puzzles" element={<Puzzles />} />
          <Route path="/sparring" element={<Sparring />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
