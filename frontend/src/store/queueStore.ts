/**
 * RetailFlow AI — Queue Zustand Store
 * 
 * Holds the live queue state for the active store.
 * Updated via WebSocket events or REST polling fallback.
 */
import { create } from "zustand";
import type { StoreQueueState, CounterQueueState } from "@/types/queue";
import type { WsQueueUpdateEvent } from "@/types/websocket";

interface QueueState {
  storeState: StoreQueueState | null;
  wsStatus: "disconnected" | "connecting" | "connected" | "error";
  lastPolledAt: string | null;
  isPolling: boolean;
  
  // Actions
  setStoreState: (state: StoreQueueState) => void;
  setWsStatus: (status: "disconnected" | "connecting" | "connected" | "error") => void;
  setIsPolling: (isPolling: boolean) => void;
  
  // Real-time updaters
  applyWsUpdate: (event: WsQueueUpdateEvent) => void;
  reset: () => void;
}

export const useQueueStore = create<QueueState>((set) => ({
  storeState: null,
  wsStatus: "disconnected",
  lastPolledAt: null,
  isPolling: false,

  setStoreState: (state) => set({ storeState: state, lastPolledAt: new Date().toISOString() }),
  setWsStatus: (status) => set({ wsStatus: status }),
  setIsPolling: (isPolling) => set({ isPolling }),

  applyWsUpdate: (event) => set((state) => {
    if (!state.storeState) return state;
    
    // Create new counters array
    const newCounters = state.storeState.counters.map(counter => {
      if (counter.counter_id === event.counter_id) {
        return {
          ...counter,
          queue_length: event.queue_length,
          estimated_wait_seconds: event.estimated_wait_seconds,
          // Format estimated wait (naive fallback format, API usually handles this but we need to do it client side for WS)
          estimated_wait_formatted: event.estimated_wait_seconds 
            ? `${Math.ceil(event.estimated_wait_seconds / 60)} min`
            : "0 min",
          status: event.status as CounterQueueState["status"],
          last_updated: event.timestamp,
          source: event.source as CounterQueueState["source"],
        };
      }
      return counter;
    });

    // Recalculate store totals
    const openCounters = newCounters.filter(c => c.status === "open").length;
    const totalCustomers = newCounters.reduce((sum, c) => sum + c.queue_length, 0);
    
    // Average wait calculation (naive client side approx, backend will correct on poll)
    let avgWait: number | null = null;
    const countersWithWait = newCounters.filter(c => c.estimated_wait_seconds !== null);
    if (countersWithWait.length > 0) {
      avgWait = countersWithWait.reduce((sum, c) => sum + (c.estimated_wait_seconds || 0), 0) / countersWithWait.length;
    }

    return {
      storeState: {
        ...state.storeState,
        counters: newCounters,
        open_counters: openCounters,
        total_customers_waiting: totalCustomers,
        avg_wait_seconds: avgWait,
        avg_wait_formatted: avgWait ? `${Math.ceil(avgWait / 60)} min` : "0 min",
        last_updated: event.timestamp,
      }
    };
  }),

  reset: () => set({ storeState: null, wsStatus: "disconnected", lastPolledAt: null, isPolling: false }),
}));
