import { createRootRoute, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import Header from "../components/Header";

const RootLayout = () => (
  <div className="flex min-h-dvh flex-col">
    <Header />
    <main id="main" className="flex flex-1 flex-col">
      <Outlet />
    </main>
    <footer className="border-t border-line px-4 py-5 text-center text-xs text-muted">
      RLCS replay data via Ballchasing.com · Educational use only do not use for
      official scouting or roster decisions
    </footer>
    <TanStackRouterDevtools />
  </div>
);

export const Route = createRootRoute({ component: RootLayout });
