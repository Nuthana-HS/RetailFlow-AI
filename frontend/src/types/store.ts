/**
 * RetailFlow AI — Store & Counter Types
 * Mirrors backend app/schemas/store.py
 */
import type { PaginationMeta } from "./api";

export type CounterStatus = "open" | "closed" | "break";

export interface Store {
  id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  total_counters: number;
  open_counters: number;
  opens_at: string | null;  // "HH:MM" or null
  closes_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Counter {
  id: string;
  store_id: string;
  counter_number: number;
  label: string | null;
  status: CounterStatus;
  cashier: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManagerSummary {
  id: string;
  email: string;
  full_name: string;
}

export interface StoreDetail extends Store {
  managers: ManagerSummary[];
  counters: Counter[];
}

export interface StoreListResponse {
  items: Store[];
  meta: PaginationMeta;
}

export interface StoreCreateRequest {
  name: string;
  address: string;
  city: string;
  state: string;
  total_counters: number;
  opens_at?: string;
  closes_at?: string;
}

export interface StoreUpdateRequest {
  name?: string;
  address?: string;
  city?: string;
  state?: string;
  total_counters?: number;
  opens_at?: string;
  closes_at?: string;
  is_active?: boolean;
}

export interface CounterCreateRequest {
  counter_number: number;
  label?: string;
}

export interface CounterUpdateRequest {
  label?: string;
  status?: CounterStatus;
  cashier?: string;
}
