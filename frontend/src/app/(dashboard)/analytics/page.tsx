import type { Metadata } from "next";
import AnalyticsDashboard from "./AnalyticsDashboard";

export const metadata: Metadata = {
  title: "Analytics | RetailFlow AI",
  description: "Historical queue performance and predictive trends.",
};

export default function AnalyticsPage() {
  return <AnalyticsDashboard />;
}
