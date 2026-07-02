/**
 * RetailFlow AI — useLiveQueue Hook
 * 
 * The central brain for the live dashboard.
 * 1. Checks if we have an activeStoreId
 * 2. Fetches the initial full state via REST
 * 3. Connects to the WebSocket for that store
 * 4. Listens for WebSocket events -> updates queueStore
 * 5. Falls back to polling if WS disconnects
 */
"use client";

import { useEffect, useCallback, useRef } from "react";
import { useQueueStore } from "@/store/queueStore";
import { useStoreStore } from "@/store/storeStore";
import { wsClient } from "@/lib/api/websocket";
import * as queueApi from "@/lib/api/queue";
import { POLL_INTERVALS } from "@/lib/constants";

export function useLiveQueue() {
  const { activeStoreId } = useStoreStore();
  const { 
    storeState, 
    wsStatus, 
    isPolling,
    setStoreState, 
    setWsStatus, 
    applyWsUpdate, 
    setIsPolling,
    reset 
  } = useQueueStore();

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch full state (REST)
  const fetchState = useCallback(async (storeId: string) => {
    try {
      const res = await queueApi.getStoreQueueState(storeId);
      setStoreState(res.data);
    } catch (err) {
      console.error("[LiveQueue] Failed to fetch state", err);
    }
  }, [setStoreState]);

  // Handle store change
  useEffect(() => {
    if (!activeStoreId) {
      wsClient.disconnect();
      reset();
      return;
    }

    // 1. Initial REST fetch
    void fetchState(activeStoreId);

    // 2. Connect WebSocket
    wsClient.connect(activeStoreId);

    // Cleanup on unmount or store change
    return () => {
      wsClient.disconnect();
    };
  }, [activeStoreId, fetchState, reset]);

  // Handle WebSocket subscriptions
  useEffect(() => {
    if (!activeStoreId) return;

    // Listen to status changes
    const unsubStatus = wsClient.onStatusChange((status) => {
      setWsStatus(status);
      
      // If error/disconnected, start polling fallback
      if ((status === "error" || status === "disconnected") && !isPolling) {
        setIsPolling(true);
      } else if (status === "connected" && isPolling) {
        setIsPolling(false);
        // Do one fresh fetch when WS reconnects to catch up on missed events
        void fetchState(activeStoreId);
      }
    });

    // Listen to messages
    const unsubMessage = wsClient.onMessage((event) => {
      if (event.event_type === "queue_update") {
        applyWsUpdate(event);
      } else if (event.event_type === "connected") {
        // Connected event gives us a baseline, we fetch state to be safe
        void fetchState(activeStoreId);
      }
    });

    return () => {
      unsubStatus();
      unsubMessage();
    };
  }, [activeStoreId, isPolling, applyWsUpdate, setWsStatus, setIsPolling, fetchState]);

  // Fallback Polling logic
  useEffect(() => {
    if (isPolling && activeStoreId) {
      console.log(`[LiveQueue] Polling started (fallback)`);
      pollIntervalRef.current = setInterval(() => {
        void fetchState(activeStoreId);
      }, POLL_INTERVALS.QUEUE);
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        console.log(`[LiveQueue] Polling stopped`);
      }
    }

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [isPolling, activeStoreId, fetchState]);

  // API exposed to the UI
  return {
    storeState,
    wsStatus,
    isPolling,
    // Expose mutation wrapper for manual updates
    manualUpdate: async (counterId: string, queueLength: number) => {
      if (!activeStoreId) return;
      await queueApi.updateCounterQueue(activeStoreId, counterId, {
        queue_length: queueLength,
        source: "manual",
      });
      // The update will flow back to us via WebSocket or Polling
    }
  };
}
