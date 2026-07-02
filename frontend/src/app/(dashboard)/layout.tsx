/**
 * Dashboard layout — Protected (requires auth)
 * Wraps all manager/admin pages with the sidebar + topbar shell.
 * Session hydration happens here.
 */
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar + Topbar will be added in Milestone 2 */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
