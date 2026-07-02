"use client"

import Link from "next/link"
import { Plus, Store as StoreIcon, AlertCircle, Clock, CheckCircle2 } from "lucide-react"

import { useStores } from "@/hooks/useStores"
import { useStoreStore } from "@/store/storeStore"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"

export default function StoresList() {
  const { data: storesRes, isLoading, error } = useStores()
  const { activeStoreId, setActiveStoreId } = useStoreStore()

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-destructive/20 bg-destructive/5 text-destructive">
        <div className="text-center space-y-2">
          <AlertCircle className="mx-auto h-8 w-8 opacity-80" />
          <p className="font-medium">Failed to load stores</p>
        </div>
      </div>
    )
  }

  const stores = storesRes?.data?.items || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Stores</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your retail locations and counters.
          </p>
        </div>
        <Button asChild>
          <Link href="/stores/new" className="gap-2">
            <Plus className="h-4 w-4" />
            Add Store
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-xl" />
          ))}
        </div>
      ) : stores.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <StoreIcon className="h-6 w-6 text-primary" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-foreground">No stores found</h3>
          <p className="mt-1 text-sm text-muted-foreground max-w-sm">
            Get started by adding your first retail location to monitor queue analytics.
          </p>
          <Button asChild className="mt-6 gap-2">
            <Link href="/stores/new">
              <Plus className="h-4 w-4" />
              Add your first store
            </Link>
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {stores.map((store) => {
            const isActive = activeStoreId === store.id

            return (
              <div
                key={store.id}
                className={`group relative overflow-hidden rounded-xl border p-5 transition-all hover:shadow-md ${
                  isActive
                    ? "border-primary/50 bg-primary/5 ring-1 ring-primary/20"
                    : "border-border bg-card hover:border-primary/30"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                        store.is_active
                          ? "bg-primary/10 text-primary"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      <StoreIcon className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground line-clamp-1">
                        {store.name}
                      </h3>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                        {store.city}, {store.state}
                      </p>
                    </div>
                  </div>
                  <Badge variant={store.is_active ? "default" : "secondary"}>
                    {store.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-4 divide-x divide-border border-y border-border py-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Open Counters</p>
                    <p className="mt-1 text-lg font-semibold text-foreground">
                      {store.open_counters} <span className="text-sm font-normal text-muted-foreground">/ {store.total_counters}</span>
                    </p>
                  </div>
                  <div className="pl-4">
                    <p className="text-xs text-muted-foreground">Hours</p>
                    <div className="mt-1 flex items-center gap-1.5 text-sm font-medium text-foreground">
                      <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                      {store.opens_at && store.closes_at
                        ? `${store.opens_at} - ${store.closes_at}`
                        : "24/7"}
                    </div>
                  </div>
                </div>

                <div className="mt-5 flex items-center gap-3">
                  <Button
                    variant={isActive ? "secondary" : "outline"}
                    className={`flex-1 gap-2 ${isActive ? "bg-primary/10 text-primary hover:bg-primary/20 border-primary/20" : ""}`}
                    onClick={() => setActiveStoreId(store.id)}
                  >
                    {isActive ? (
                      <>
                        <CheckCircle2 className="h-4 w-4" />
                        Selected
                      </>
                    ) : (
                      "Select Context"
                    )}
                  </Button>
                  <Button variant="outline" asChild className="flex-1">
                    <Link href={`/stores/${store.id}`}>Manage</Link>
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
