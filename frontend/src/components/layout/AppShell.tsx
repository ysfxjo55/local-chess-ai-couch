import { Outlet } from "react-router-dom";
import { NavBar } from "./NavBar";
import { MobileTabBar } from "./MobileTabBar";
import { MobileTopBar } from "./MobileTopBar";

export function AppShell() {
  return (
    <div className="min-h-dvh bg-obsidian">
      <NavBar />
      <MobileTopBar />
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 md:px-6 md:pb-10">
        <Outlet />
      </main>
      <MobileTabBar />
    </div>
  );
}
