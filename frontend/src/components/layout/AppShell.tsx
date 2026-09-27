import { Outlet } from "react-router-dom";
import { NavBar } from "./NavBar";
import { MobileTabBar } from "./MobileTabBar";
import { MobileTopBar } from "./MobileTopBar";

export function AppShell() {
  return (
    <div className="min-h-dvh bg-obsidian">
      <a href="#main-content" className="sr-only z-50 rounded-md bg-amber px-3 py-2 text-sm font-semibold text-obsidian focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Skip to main content</a>
      <NavBar />
      <MobileTopBar />
      <main id="main-content" tabIndex={-1} className="mx-auto max-w-6xl px-4 pb-24 pt-6 outline-none md:px-6 md:pb-10">
        <Outlet />
      </main>
      <MobileTabBar />
    </div>
  );
}
