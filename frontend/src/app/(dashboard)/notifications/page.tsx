import type { Metadata } from "next";
import NotificationsList from "./NotificationsList";

export const metadata: Metadata = {
  title: "Notifications | RetailFlow AI",
  description: "System alerts and queue threshold triggers.",
};

export default function NotificationsPage() {
  return <NotificationsList />;
}
