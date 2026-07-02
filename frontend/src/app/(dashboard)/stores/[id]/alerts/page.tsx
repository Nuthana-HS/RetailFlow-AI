import type { Metadata } from "next";
import StoreAlerts from "./StoreAlerts";

export const metadata: Metadata = {
  title: "Alerts | RetailFlow AI",
};

export default function StoreAlertsPage() {
  return <StoreAlerts />;
}
