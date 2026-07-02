import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard | RetailFlow AI",
  description: "Real-time queue management dashboard.",
};

export default function DashboardPage() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <p className="text-muted-foreground text-sm">
        Loading dashboard… (full UI arrives in Milestone 3)
      </p>
    </div>
  );
}
