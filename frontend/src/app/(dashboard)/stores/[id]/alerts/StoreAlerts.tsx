"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft, AlertCircle, Plus, Settings2, Bell } from "lucide-react"

import { useStore } from "@/hooks/useStores"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function StoreAlerts() {
  const params = useParams<{ id: string }>()
  const { data: storeRes, isLoading, error } = useStore(params.id)

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-destructive/20 bg-destructive/5 text-destructive">
        <div className="text-center space-y-2">
          <AlertCircle className="mx-auto h-8 w-8 opacity-80" />
          <p className="font-medium">Failed to load store</p>
          <Button variant="outline" asChild className="mt-4 border-destructive/30 hover:bg-destructive/10">
            <Link href="/stores">Back to Stores</Link>
          </Button>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    )
  }

  const store = storeRes?.data
  if (!store) return null

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild className="rounded-full">
          <Link href={`/stores/${store.id}`}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div className="flex-1 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
              Alert Configurations
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Manage proactive notifications for {store.name}
            </p>
          </div>
          <Button className="gap-2 shrink-0">
            <Plus className="h-4 w-4" />
            New Alert
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <div className="p-6 border-b border-border bg-muted/20">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <Settings2 className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">How alerts work</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                Configure thresholds for queue length or wait times. When a threshold is exceeded, 
                all managers assigned to this store will receive a real-time notification.
              </p>
            </div>
          </div>
        </div>

        <div className="p-0">
          {/* Placeholder for alerts list - for Milestone 2 we just show empty state */}
          <div className="flex flex-col items-center justify-center py-16 text-center px-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Bell className="h-6 w-6 text-muted-foreground" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-foreground">No alerts configured</h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm">
              You haven&apos;t set up any threshold alerts for this store yet.
            </p>
            <Button className="mt-6 gap-2" variant="outline">
              <Plus className="h-4 w-4" />
              Create your first alert
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
