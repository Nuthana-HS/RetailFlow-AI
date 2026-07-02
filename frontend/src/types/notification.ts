/**
 * RetailFlow AI — Notification Types
 * Mirrors backend app/schemas/notification.py
 */

export type NotificationSeverity = "info" | "warning" | "critical";

export interface NotificationItem {
  id: string;
  user_id: string;
  store_id: string | null;
  counter_id: string | null;
  title: string;
  message: string;
  severity: NotificationSeverity;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationInboxResponse {
  notifications: NotificationItem[];
  total: number;
  unread_count: number;
  page: number;
  limit: number;
}

export interface UnreadCountResponse {
  unread_count: number;
  user_id: string;
}
