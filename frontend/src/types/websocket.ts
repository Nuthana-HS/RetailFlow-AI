/**
 * RetailFlow AI — WebSocket Event Types
 * Mirrors backend app/schemas/queue.py QueueUpdateEvent
 */

export type WsEventType = "connected" | "queue_update" | "counter_status" | "alert" | "pong";

export interface WsConnectedEvent {
  event_type: "connected";
  store_id: string;
  message: string;
  timestamp: string;
}

export interface WsQueueUpdateEvent {
  event_type: "queue_update";
  store_id: string;
  counter_id: string;
  queue_length: number;
  estimated_wait_seconds: number | null;
  counter_number: number;
  status: string;
  timestamp: string;
  source: string;
}

export interface WsPongEvent {
  event_type: "pong";
  timestamp: string;
}

export type WsEvent = WsConnectedEvent | WsQueueUpdateEvent | WsPongEvent;

export interface WsPingMessage {
  type: "ping";
}
