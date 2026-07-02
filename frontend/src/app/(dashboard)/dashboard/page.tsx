import type { Metadata } from "next";
import LiveDashboard from "./LiveDashboard";

export const metadata: Metadata = {
  title: "Dashboard | RetailFlow AI",
  description: "Real-time queue management dashboard.",
};

export default function DashboardPage() {
  return <LiveDashboard />;
}
