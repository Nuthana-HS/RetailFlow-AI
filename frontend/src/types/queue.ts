/**
 * RetailFlow AI — Queue Engine Types
 * Mirrors backend app/schemas/queue.py
 */
import type { CounterStatus } from "./store";

export type QueueUpdateSource = "manual" | "cv" | "simulation";
export type AlertType = "queue_length" | "wait_time";

export interface CounterQueueState {
  counter_id: string;
  counter_number: number;
  label: string | null;
  status: CounterStatus;
  queue_length: number;
  estimated_wait_seconds: number | null;
  estimated_wait_formatted: string;
  last_updated: string | null;
  source: QueueUpdateSource | null;
}

export interface StoreQueueState {
  store_id: string;
  store_name: string;
  total_customers_waiting: number;
  open_counters: number;
  avg_wait_seconds: number | null;
  avg_wait_formatted: string;
  alert_active: boolean;
  counters: CounterQueueState[];
  last_updated: string | null;
}

export interface QueueUpdateRequest {
  queue_length: number;
  source?: QueueUpdateSource;
  note?: string;
}

export interface AlertConfig {
  id: string;
  store_id: string;
  counter_id: string | null;
  alert_type: AlertType;
  threshold: number;
  cooldown_minutes: number;
  is_active: boolean;
  last_triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertConfigRequest {
  alert_type: AlertType;
  threshold: number;
  counter_id?: string;
  cooldown_minutes?: number;
  is_active?: boolean;
}

export interface QueueSnapshotResponse {
  id: string;
  counter_id: string | null;
  store_id: string;
  queue_length: number;
  estimated_wait_seconds: number | null;
  source: QueueUpdateSource;
  recorded_at: string;
}

export interface QueueHistoryResponse {
  snapshots: QueueSnapshotResponse[];
  total: number;
  page: number;
  limit: number;
}
