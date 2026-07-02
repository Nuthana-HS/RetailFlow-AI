"use client"

import { useEffect } from "react"
import Link from "next/link"
import { Store, Wifi, WifiOff, Activity, Users, Clock, AlertTriangle } from "lucide-react"

import { useLiveQueue } from "@/hooks/useLiveQueue"
import { useStoreStore } from "@/store/storeStore"
import { useStores } from "@/hooks/useStores"
import { CounterCard } from "@/components/dashboard/CounterCard"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/cn"

export default function LiveDashboard() {
  const { activeStoreId, setActiveStoreId } = useStoreStore()
  const { data: storesRes, isLoading: isLoadingStores } = useStores({ is_active: true })
  
  const { storeState, wsStatus, isPolling, manualUpdate } = useLiveQueue()
  
  // Auto-select first store if none selected
  useEffect(() => {
    if (!activeStoreId && storesRes?.data?.items && storesRes.data.items.length > 0) {
      setActiveStoreId(storesRes.data.items[0].id)
    }
  }, [activeStoreId, storesRes, setActiveStoreId])

  if (isLoadingStores) {
    return (
      <div className="space-y-6 p-1">
        <Skeleton className="h-12 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-48 rounded-xl" />)}
        </div>
      </div>
    )
  }

  const stores = storesRes?.data?.items || []

  if (stores.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-24 text-center">
        <Store className="h-12 w-12 text-muted-foreground mb-4" />
        <h2 className="text-xl font-semibold">No Active Stores</h2>
        <p className="text-muted-foreground mt-2 max-w-md">
          You need an active store to view the live dashboard. Go to the stores page to add one.
        </p>
        <Button asChild className="mt-6">
          <Link href="/stores/new">Add Store</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-fade-in pb-8">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
            Live Queue Monitor
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time operations view and manual overrides.
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Store Selector */}
          <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-1">
            {stores.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveStoreId(s.id)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-all",
                  activeStoreId === s.id
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                {s.name}
              </button>
            ))}
          </div>
          
          {/* Connection Status Badge */}
          <div className={cn(
            "flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-medium shadow-sm transition-colors",
            wsStatus === "connected" ? "border-success/30 bg-success/10 text-success" : 
            wsStatus === "error" ? "border-destructive/30 bg-destructive/10 text-destructive" :
            "border-warning/30 bg-warning/10 text-warning"
          )}>
            {wsStatus === "connected" ? <Wifi className="h-3.5 w-3.5" /> : 
             wsStatus === "error" ? <WifiOff className="h-3.5 w-3.5" /> :
             <Activity className="h-3.5 w-3.5 animate-pulse" />}
            
            <span className="capitalize">
              {wsStatus === "error" ? "Disconnected" : wsStatus}
            </span>
            
            {isPolling && (
              <span className="ml-1 flex items-center gap-1 rounded-sm bg-background/50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wider text-muted-foreground opacity-80">
                POLLING
              </span>
            )}
          </div>
        </div>
      </div>

      {!storeState ? (
        <div className="flex h-64 items-center justify-center rounded-xl border border-dashed bg-card/50">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Activity className="h-8 w-8 animate-pulse" />
            <p>Waiting for queue state...</p>
          </div>
        </div>
      ) : (
        <>
          {/* Top Level Metrics */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <div className="flex items-center gap-2 text-muted-foreground mb-3">
                <Users className="h-4 w-4" />
                <h3 className="text-sm font-medium">Total Waiting</h3>
              </div>
              <p className="counter-flip text-3xl font-bold tracking-tight text-foreground">
                {storeState.total_customers_waiting}
              </p>
            </div>
            
            <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <div className="flex items-center gap-2 text-muted-foreground mb-3">
                <Store className="h-4 w-4" />
                <h3 className="text-sm font-medium">Open Counters</h3>
              </div>
              <p className="text-3xl font-bold tracking-tight text-foreground">
                {storeState.open_counters} <span className="text-lg font-normal text-muted-foreground">/ {storeState.counters.length}</span>
              </p>
            </div>
            
            <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <div className="flex items-center gap-2 text-muted-foreground mb-3">
                <Clock className="h-4 w-4" />
                <h3 className="text-sm font-medium">Avg Wait Time</h3>
              </div>
              <p className="counter-flip text-3xl font-bold tracking-tight text-foreground">
                {storeState.avg_wait_formatted}
              </p>
            </div>
            
            <div className={cn(
              "rounded-xl border p-5 shadow-sm transition-colors duration-300",
              storeState.alert_active 
                ? "border-destructive bg-destructive/10" 
                : "border-border bg-card"
            )}>
              <div className={cn(
                "flex items-center gap-2 mb-3",
                storeState.alert_active ? "text-destructive" : "text-muted-foreground"
              )}>
                <AlertTriangle className="h-4 w-4" />
                <h3 className="text-sm font-medium">Alert Status</h3>
              </div>
              <p className={cn(
                "text-2xl font-bold tracking-tight",
                storeState.alert_active ? "text-destructive animate-pulse" : "text-foreground"
              )}>
                {storeState.alert_active ? "Triggered" : "Normal"}
              </p>
            </div>
          </div>

          {/* Counters Grid */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold tracking-tight text-foreground flex items-center justify-between">
              Counter Activity
              <span className="text-xs font-normal text-muted-foreground bg-muted px-2 py-1 rounded-full">
                {storeState.last_updated ? new Date(storeState.last_updated).toLocaleTimeString() : "Never"}
              </span>
            </h2>
            <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {storeState.counters
                .sort((a, b) => a.counter_number - b.counter_number)
                .map((counter) => (
                  <CounterCard 
                    key={counter.counter_id} 
                    counter={counter} 
                    onManualUpdate={manualUpdate}
                  />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
