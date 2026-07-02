"use client"

import { useState } from "react"
import { Bell, CheckCheck, Loader2, Info, AlertTriangle, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react"

import { useNotifications, useMarkAllAsRead, useMarkAsRead } from "@/hooks/useNotifications"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/cn"
import type { NotificationSeverity } from "@/types/notification"

const SEVERITY_ICONS: Record<NotificationSeverity, React.ElementType> = {
  info: Info,
  warning: AlertTriangle,
  critical: AlertCircle,
}

const SEVERITY_COLORS: Record<NotificationSeverity, string> = {
  info: "text-primary bg-primary/10",
  warning: "text-warning bg-warning/10",
  critical: "text-destructive bg-destructive/10",
}

export default function NotificationsList() {
  const [page, setPage] = useState(1)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const limit = 20

  const { data: res, isLoading, error } = useNotifications({ 
    page, 
    limit, 
    unread_only: unreadOnly 
  })
  
  const markAsRead = useMarkAsRead()
  const markAllAsRead = useMarkAllAsRead()

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-destructive/20 bg-destructive/5 text-destructive">
        <div className="text-center space-y-2">
          <AlertCircle className="mx-auto h-8 w-8 opacity-80" />
          <p className="font-medium">Failed to load notifications</p>
        </div>
      </div>
    )
  }

  const notifications = res?.data?.notifications || []
  const meta = res?.data || { total: 0, page: 1, limit: 20 }
  const totalPages = Math.ceil(meta.total / meta.limit)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <Bell className="h-6 w-6 text-muted-foreground" />
            Notifications
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            System alerts and queue threshold triggers.
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="flex rounded-md border border-border p-1 bg-card">
            <button
              onClick={() => { setUnreadOnly(false); setPage(1) }}
              className={cn(
                "rounded px-3 py-1.5 text-xs font-medium transition-colors",
                !unreadOnly ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"
              )}
            >
              All
            </button>
            <button
              onClick={() => { setUnreadOnly(true); setPage(1) }}
              className={cn(
                "rounded px-3 py-1.5 text-xs font-medium transition-colors",
                unreadOnly ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"
              )}
            >
              Unread
            </button>
          </div>
          
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => markAllAsRead.mutate()}
            disabled={markAllAsRead.isPending || (res?.data?.unread_count === 0)}
            className="gap-2"
          >
            {markAllAsRead.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCheck className="h-4 w-4" />}
            Mark all read
          </Button>
        </div>
      </div>

      {/* List */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="divide-y divide-border">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="p-4 flex gap-4">
                <Skeleton className="h-10 w-10 rounded-full shrink-0" />
                <div className="space-y-2 w-full">
                  <Skeleton className="h-5 w-1/3" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              </div>
            ))}
          </div>
        ) : notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center px-4">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-muted/50 mb-4">
              <Bell className="h-8 w-8 text-muted-foreground opacity-50" />
            </div>
            <h3 className="text-lg font-semibold text-foreground">No notifications</h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm">
              {unreadOnly 
                ? "You've read all your notifications." 
                : "When queue thresholds are crossed, alerts will appear here."}
            </p>
            {unreadOnly && (
              <Button variant="link" onClick={() => setUnreadOnly(false)} className="mt-4">
                View all notifications
              </Button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {notifications.map((notif) => {
              const Icon = SEVERITY_ICONS[notif.severity]
              const colors = SEVERITY_COLORS[notif.severity]
              
              return (
                <div 
                  key={notif.id}
                  className={cn(
                    "flex items-start gap-4 p-5 transition-colors",
                    !notif.is_read ? "bg-primary/5 hover:bg-primary/10" : "bg-card hover:bg-muted/50"
                  )}
                >
                  <div className={cn("mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full", colors)}>
                    <Icon className="h-5 w-5" />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <h4 className={cn(
                        "font-semibold text-base",
                        !notif.is_read ? "text-foreground" : "text-muted-foreground"
                      )}>
                        {notif.title}
                      </h4>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {new Date(notif.created_at).toLocaleString()}
                      </span>
                    </div>
                    
                    <p className={cn(
                      "text-sm mb-2",
                      !notif.is_read ? "text-foreground/90" : "text-muted-foreground"
                    )}>
                      {notif.message}
                    </p>
                    
                    {notif.store_id && (
                      <Badge variant="outline" className="text-[10px] font-normal mr-2">
                        Store Config
                      </Badge>
                    )}
                  </div>
                  
                  <div className="shrink-0 flex items-center justify-end w-24">
                    {!notif.is_read ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                        onClick={() => markAsRead.mutate(notif.id)}
                        disabled={markAsRead.isPending}
                      >
                        Mark read
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <CheckCheck className="h-3 w-3" />
                        Read
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border p-4 bg-muted/20">
            <p className="text-sm text-muted-foreground">
              Showing {(page - 1) * limit + 1} to Math.min(page * limit, meta.total) of {meta.total}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1 || isLoading}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm font-medium px-2">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || isLoading}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
