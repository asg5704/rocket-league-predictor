import { createRootRoute, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import Header from "../components/Header";

const RootLayout = () => (
  <main className="min-h-screen bg-bkg flex flex-col">
    <Header />
    <Outlet />
    <TanStackRouterDevtools />
  </main>
);

export const Route = createRootRoute({ component: RootLayout });
