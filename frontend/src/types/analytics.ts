/**
 * RetailFlow AI — Analytics Response Types
 * Mirrors backend app/schemas/analytics.py
 */

export interface StoreSummaryAnalytics {
  store_id: string;
  store_name: string;
  period_from: string;
  period_to: string;
  total_snapshots: number;
  total_customers_estimated: number;
  avg_queue_length: number;
  peak_queue_length: number;
  avg_wait_seconds: number | null;
  avg_wait_formatted: string;
  peak_wait_seconds: number | null;
  busiest_hour: number | null;
  busiest_day_of_week: string | null;
  active_counters: number;
  cached: boolean;
}

export interface HeatmapCell {
  day_of_week: number;    // 0=Sunday … 6=Saturday
  day_name: string;
  hour_of_day: number;    // 0–23
  avg_queue_length: number;
  sample_count: number;
  intensity: number;      // 0.0–1.0
}

export interface PeakHoursHeatmap {
  store_id: string;
  store_name: string;
  days_back: number;
  cells: HeatmapCell[];
  max_avg_queue: number;
  cached: boolean;
}

export interface TrendBucket {
  bucket_time: string;
  counter_id: string | null;
  counter_number: number | null;
  avg_queue_length: number;
  max_queue_length: number;
  sample_count: number;
}

export interface QueueTrendsResponse {
  store_id: string;
  store_name: string;
  from_dt: string;
  to_dt: string;
  bucket_minutes: number;
  buckets: TrendBucket[];
  cached: boolean;
}

export interface CounterStats {
  counter_id: string;
  counter_number: number;
  label: string | null;
  avg_queue_length: number;
  peak_queue_length: number;
  avg_wait_seconds: number | null;
  avg_wait_formatted: string;
  total_updates: number;
  efficiency_rank: number;
}

export interface CounterComparisonResponse {
  store_id: string;
  store_name: string;
  period_from: string;
  period_to: string;
  counters: CounterStats[];
  cached: boolean;
}
