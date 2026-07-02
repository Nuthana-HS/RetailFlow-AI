/**
 * RetailFlow AI — Notifications Zustand Store
 * 
 * Tracks the global unread count and manages periodic polling.
 */
import { create } from "zustand";
import * as notificationsApi from "@/lib/api/notifications";

interface NotificationState {
  unreadCount: number;
  lastPolledAt: string | null;
  isPolling: boolean;
  
  // Actions
  setUnreadCount: (count: number) => void;
  decrementUnread: () => void;
  resetUnread: () => void;
  setIsPolling: (isPolling: boolean) => void;
  
  // API triggers
  fetchUnreadCount: () => Promise<void>;
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  unreadCount: 0,
  lastPolledAt: null,
  isPolling: false,

  setUnreadCount: (count) => set({ unreadCount: count, lastPolledAt: new Date().toISOString() }),
  
  decrementUnread: () => set((state) => ({ 
    unreadCount: Math.max(0, state.unreadCount - 1) 
  })),
  
  resetUnread: () => set({ unreadCount: 0 }),
  
  setIsPolling: (isPolling) => set({ isPolling }),

  fetchUnreadCount: async () => {
    try {
      const res = await notificationsApi.getUnreadCount();
      get().setUnreadCount(res.data.unread_count);
    } catch (err) {
      console.error("[NotificationStore] Failed to fetch unread count", err);
    }
  },
}));
