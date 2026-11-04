import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/roads/$roadId")({
  component: () => <Outlet />,
});
