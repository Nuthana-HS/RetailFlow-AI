"use client"

import { useRouter } from "next/navigation"
import Link from "next/link"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { ArrowLeft, Loader2, Store as StoreIcon } from "lucide-react"

import { useCreateStore } from "@/hooks/useStores"
import type { StoreCreateRequest } from "@/types/store"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"

// ─── Form Schema ─────────────────────────────────────────────────────────────
const storeSchema = z.object({
  name: z.string().min(2, "Store name is required"),
  address: z.string().min(5, "Address is required"),
  city: z.string().min(2, "City is required"),
  state: z.string().min(2, "State is required"),
  total_counters: z.coerce.number().min(1).max(50),
  opens_at: z.string().regex(/^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/, "Must be HH:MM format").optional().or(z.literal("")),
  closes_at: z.string().regex(/^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/, "Must be HH:MM format").optional().or(z.literal("")),
})

type StoreFormValues = z.infer<typeof storeSchema>

export default function NewStoreForm() {
  const router = useRouter()
  const createStore = useCreateStore()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<StoreFormValues>({
    resolver: zodResolver(storeSchema),
    defaultValues: {
      total_counters: 5,
    },
  })

  const onSubmit = async (values: StoreFormValues) => {
    try {
      // Build payload and omit empty optional fields
      const payload: Partial<StoreFormValues> = { ...values }
      if (!payload.opens_at) delete payload.opens_at
      if (!payload.closes_at) delete payload.closes_at
      
      await createStore.mutateAsync(payload as StoreCreateRequest)
      router.push("/stores")
    } catch {
      // error is handled in mutation
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild className="rounded-full">
          <Link href="/stores">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Add New Store</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Register a new retail location to monitor.
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <StoreIcon className="h-6 w-6" />
        </div>
        
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-4">
            {/* Store Name */}
            <div className="space-y-1.5">
              <label htmlFor="name" className="text-sm font-medium">Store Name</label>
              <input
                id="name"
                type="text"
                placeholder="e.g. Downtown Flagship"
                className={cn(
                  "w-full rounded-lg border bg-background px-3 py-2 text-sm",
                  "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
                  errors.name ? "border-destructive" : "border-input"
                )}
                {...register("name")}
              />
              {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            </div>

            {/* Address */}
            <div className="space-y-1.5">
              <label htmlFor="address" className="text-sm font-medium">Address</label>
              <input
                id="address"
                type="text"
                placeholder="123 Main St"
                className={cn(
                  "w-full rounded-lg border bg-background px-3 py-2 text-sm",
                  "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
                  errors.address ? "border-destructive" : "border-input"
                )}
                {...register("address")}
              />
              {errors.address && <p className="text-xs text-destructive">{errors.address.message}</p>}
            </div>

            {/* City / State */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label htmlFor="city" className="text-sm font-medium">City</label>
                <input
                  id="city"
                  type="text"
                  placeholder="San Francisco"
                  className={cn(
                    "w-full rounded-lg border bg-background px-3 py-2 text-sm",
                    "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
                    errors.city ? "border-destructive" : "border-input"
                  )}
                  {...register("city")}
                />
                {errors.city && <p className="text-xs text-destructive">{errors.city.message}</p>}
              </div>
              <div className="space-y-1.5">
                <label htmlFor="state" className="text-sm font-medium">State / Region</label>
                <input
                  id="state"
                  type="text"
                  placeholder="CA"
                  className={cn(
                    "w-full rounded-lg border bg-background px-3 py-2 text-sm",
                    "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
                    errors.state ? "border-destructive" : "border-input"
                  )}
                  {...register("state")}
                />
                {errors.state && <p className="text-xs text-destructive">{errors.state.message}</p>}
              </div>
            </div>
            
            <div className="my-6 border-t border-border" />

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Total Counters */}
              <div className="space-y-1.5">
                <label htmlFor="total_counters" className="text-sm font-medium">Total Counters</label>
                <input
                  id="total_counters"
                  type="number"
                  min="1"
                  max="50"
                  className={cn(
                    "w-full rounded-lg border bg-background px-3 py-2 text-sm",
                    "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
                    errors.total_counters ? "border-destructive" : "border-input"
                  )}
                  {...register("total_counters")}
                />
                {errors.total_counters && <p className="text-xs text-destructive">{errors.total_counters.message}</p>}
              </div>

              {/* Opens At */}
              <div className="space-y-1.5">
                <label htmlFor="opens_at" className="text-sm font-medium text-muted-foreground">Opens At (Optional)</label>
                <input
                  id="opens_at"
                  type="time"
                  className={cn(
                    "w-full rounded-lg border bg-background px-3 py-2 text-sm",
                    "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
                    errors.opens_at ? "border-destructive" : "border-input"
                  )}
                  {...register("opens_at")}
                />
                {errors.opens_at && <p className="text-xs text-destructive">{errors.opens_at.message}</p>}
              </div>

              {/* Closes At */}
              <div className="space-y-1.5">
                <label htmlFor="closes_at" className="text-sm font-medium text-muted-foreground">Closes At (Optional)</label>
                <input
                  id="closes_at"
                  type="time"
                  className={cn(
                    "w-full rounded-lg border bg-background px-3 py-2 text-sm",
                    "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
                    errors.closes_at ? "border-destructive" : "border-input"
                  )}
                  {...register("closes_at")}
                />
                {errors.closes_at && <p className="text-xs text-destructive">{errors.closes_at.message}</p>}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={() => router.push("/stores")} disabled={createStore.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={createStore.isPending} className="gap-2">
              {createStore.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Create Store
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
