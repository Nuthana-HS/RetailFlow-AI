"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { 
  ArrowLeft, Store as StoreIcon, AlertCircle, 
  Trash2, Plus, Users, Edit2
} from "lucide-react"

import { useStore } from "@/hooks/useStores"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"

export default function StoreDetail() {
  const params = useParams<{ id: string }>()
  const { data: storeRes, isLoading, error } = useStore(params.id)
  
  if (error) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-destructive/20 bg-destructive/5 text-destructive">
        <div className="text-center space-y-2">
          <AlertCircle className="mx-auto h-8 w-8 opacity-80" />
          <p className="font-medium">Failed to load store details</p>
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
        <Skeleton className="h-48 w-full rounded-xl" />
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
          <Link href="/stores">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div className="flex-1 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <StoreIcon className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
                {store.name}
                <Badge variant={store.is_active ? "default" : "secondary"}>
                  {store.is_active ? "Active" : "Inactive"}
                </Badge>
              </h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                {store.address}, {store.city}, {store.state}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" asChild>
              <Link href={`/stores/${store.id}/alerts`}>
                <AlertCircle className="h-4 w-4 mr-2" />
                Alerts
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Details & Managers */}
        <div className="space-y-6">
          <div className="rounded-xl border border-border bg-card shadow-sm p-6 space-y-6">
            <div>
              <h3 className="font-semibold text-lg flex items-center gap-2">
                <StoreIcon className="h-5 w-5 text-muted-foreground" />
                Store Settings
              </h3>
              <p className="text-sm text-muted-foreground mt-1 mb-4">Update general store information.</p>
              
              {/* Note: In a real app we'd have a full edit form here.
                  For Milestone 2, we just show details and a placeholder edit button. */}
              
              <div className="space-y-4 rounded-lg bg-muted/30 p-4 border border-border/50">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Total Counters</span>
                  <span className="text-sm font-medium">{store.total_counters}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Hours</span>
                  <span className="text-sm font-medium">
                    {store.opens_at && store.closes_at ? `${store.opens_at} - ${store.closes_at}` : "24/7"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Created At</span>
                  <span className="text-sm font-medium">{new Date(store.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
            
            <div className="border-t border-border pt-6">
              <h3 className="font-semibold text-lg flex items-center gap-2">
                <Users className="h-5 w-5 text-muted-foreground" />
                Managers
              </h3>
              <div className="mt-4 space-y-3">
                {store.managers.length > 0 ? (
                  store.managers.map(manager => (
                    <div key={manager.id} className="flex items-center gap-3 p-3 rounded-lg border border-border/50 bg-background">
                      <div className="h-8 w-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-medium text-xs">
                        {manager.full_name.substring(0, 2).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{manager.full_name}</p>
                        <p className="text-xs text-muted-foreground truncate">{manager.email}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No managers assigned.</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Counters */}
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-xl border border-border bg-card shadow-sm p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <div>
                <h3 className="font-semibold text-lg flex items-center gap-2">
                  <Users className="h-5 w-5 text-muted-foreground" />
                  Counters
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Manage physical checkout counters at this location.
                </p>
              </div>
              <Button size="sm" className="gap-2 shrink-0">
                <Plus className="h-4 w-4" />
                Add Counter
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {store.counters.map(counter => (
                <div key={counter.id} className="flex flex-col rounded-lg border border-border bg-background p-4 transition-colors hover:border-primary/30">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground">Counter #{counter.counter_number}</span>
                        <Badge variant={counter.status === "open" ? "default" : "secondary"} className="text-[10px] px-1.5 py-0">
                          {counter.status}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {counter.label || "No label"}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full text-muted-foreground hover:text-foreground">
                        <Edit2 className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full text-muted-foreground hover:text-destructive">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  {counter.cashier && (
                    <div className="mt-3 pt-3 border-t border-border/50 text-xs text-muted-foreground flex items-center gap-1.5">
                      <Users className="h-3 w-3" />
                      Cashier: {counter.cashier}
                    </div>
                  )}
                </div>
              ))}
              
              {store.counters.length === 0 && (
                <div className="col-span-full rounded-lg border border-dashed py-8 text-center text-muted-foreground text-sm">
                  No counters configured yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
