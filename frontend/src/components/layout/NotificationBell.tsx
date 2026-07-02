"use client"

import { useEffect } from "react"
import Link from "next/link"
import { Bell, CheckCheck, Loader2 } from "lucide-react"

import { useNotificationStore } from "@/store/notificationStore"
import { useNotifications, useMarkAllAsRead, useMarkAsRead } from "@/hooks/useNotifications"
import { POLL_INTERVALS } from "@/lib/constants"
import { cn } from "@/lib/cn"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"

export function NotificationBell() {
  const { unreadCount, fetchUnreadCount } = useNotificationStore()
  
  const { data: notificationsRes, isLoading } = useNotifications({ limit: 5 })
  const markAsRead = useMarkAsRead()
  const markAllAsRead = useMarkAllAsRead()

  // Poll for unread count
  useEffect(() => {
    void fetchUnreadCount()
    
    const interval = setInterval(() => {
      void fetchUnreadCount()
    }, POLL_INTERVALS.UNREAD_COUNT)
    
    return () => clearInterval(interval)
  }, [fetchUnreadCount])

  const notifications = notificationsRes?.data?.notifications || []

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="relative flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground transition-colors outline-none">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-destructive-foreground animate-badge-pop">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      
      <DropdownMenuContent align="end" className="w-80 font-sans p-0">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <DropdownMenuLabel className="font-semibold p-0">
            Notifications
          </DropdownMenuLabel>
          {unreadCount > 0 && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="h-auto p-0 text-xs text-primary hover:text-primary/80 hover:bg-transparent"
              onClick={(e) => {
                e.preventDefault() // prevent closing menu
                markAllAsRead.mutate()
              }}
              disabled={markAllAsRead.isPending}
            >
              {markAllAsRead.isPending ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <CheckCheck className="h-3 w-3 mr-1" />}
              Mark all read
            </Button>
          )}
        </div>
        
        <div className="max-h-[300px] overflow-y-auto py-1">
          {isLoading ? (
            <div className="flex justify-center py-6 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              <Bell className="mx-auto h-8 w-8 opacity-20 mb-3" />
              <p>You&apos;re all caught up!</p>
            </div>
          ) : (
            notifications.map((notification) => (
              <DropdownMenuItem 
                key={notification.id} 
                className={cn(
                  "flex flex-col items-start gap-1 p-4 cursor-pointer focus:bg-muted whitespace-normal",
                  !notification.is_read ? "bg-primary/5" : ""
                )}
                onClick={() => {
                  if (!notification.is_read) {
                    markAsRead.mutate(notification.id)
                  }
                }}
              >
                <div className="flex items-start justify-between w-full gap-2">
                  <span className={cn(
                    "font-semibold text-sm",
                    !notification.is_read ? "text-foreground" : "text-muted-foreground"
                  )}>
                    {notification.title}
                  </span>
                  {!notification.is_read && (
                    <span className="h-2 w-2 rounded-full bg-primary shrink-0 mt-1" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {notification.message}
                </p>
                <span className="text-[10px] text-muted-foreground mt-1">
                  {new Date(notification.created_at).toLocaleString(undefined, { 
                    month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
                  })}
                </span>
              </DropdownMenuItem>
            ))
          )}
        </div>
        
        <div className="border-t border-border p-1">
          <Button variant="ghost" asChild className="w-full text-xs h-8 text-muted-foreground">
            <Link href="/notifications">View all notifications</Link>
          </Button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
