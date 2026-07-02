/**
 * Dashboard layout — Protected (requires auth)
 * Wraps all manager/admin pages with the sidebar + topbar shell.
 * Session hydration happens here.
 */
"use client";

import { useSessionHydration, useAuth } from "@/hooks/useAuth";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Loader2 } from "lucide-react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Attempt to restore session on mount
  useSessionHydration();
  
  const { isLoading, isAuthenticated } = useAuth();

  // Show a full screen loading state while checking auth
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // If not authenticated, the middleware/hook will redirect. 
  // We return null to avoid flashing protected content.
  if (!isAuthenticated) {
    return null;
  }

  return <DashboardShell>{children}</DashboardShell>;
}
