"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import * as notificationsApi from "@/lib/api/notifications"
import { useNotificationStore } from "@/store/notificationStore"

export const NOTIFICATIONS_QUERY_KEYS = {
  all: ["notifications"] as const,
  lists: () => [...NOTIFICATIONS_QUERY_KEYS.all, "list"] as const,
  list: (params: Record<string, unknown>) =>
    [...NOTIFICATIONS_QUERY_KEYS.lists(), params] as const,
}

export function useNotifications(params?: { page?: number; limit?: number; unread_only?: boolean }) {
  return useQuery({
    queryKey: NOTIFICATIONS_QUERY_KEYS.list(params ?? {}),
    queryFn: () => notificationsApi.getNotifications(params),
  })
}

export function useMarkAsRead() {
  const queryClient = useQueryClient()
  const decrementUnread = useNotificationStore((state) => state.decrementUnread)

  return useMutation({
    mutationFn: (id: string) => notificationsApi.markAsRead(id),
    onSuccess: () => {
      // Optimistically decrement global badge count
      decrementUnread()
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_QUERY_KEYS.lists() })
    },
    onError: () => {
      toast.error("Failed to mark notification as read")
    },
  })
}

export function useMarkAllAsRead() {
  const queryClient = useQueryClient()
  const resetUnread = useNotificationStore((state) => state.resetUnread)

  return useMutation({
    mutationFn: () => notificationsApi.markAllAsRead(),
    onSuccess: () => {
      resetUnread()
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_QUERY_KEYS.lists() })
      toast.success("All notifications marked as read")
    },
    onError: () => {
      toast.error("Failed to clear notifications")
    },
  })
}
