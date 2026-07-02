"use client"

import { useState } from "react"
import { Users, Clock, Loader2, Plus, Minus, Info } from "lucide-react"

import type { CounterQueueState } from "@/types/queue"
import { QUEUE_THRESHOLDS } from "@/lib/constants"
import { cn } from "@/lib/cn"
import { Button } from "@/components/ui/button"

interface CounterCardProps {
  counter: CounterQueueState
  onManualUpdate?: (counterId: string, newLength: number) => Promise<void>
}

export function CounterCard({ counter, onManualUpdate }: CounterCardProps) {
  const [isUpdating, setIsUpdating] = useState(false)

  // Determine status colour based on queue length
  let statusColor = "bg-queue-low text-queue-low-bg"
  let borderColor = "border-queue-low/30"
  let bgGradient = "from-queue-low/10 to-transparent"

  if (counter.queue_length > QUEUE_THRESHOLDS.MED_MAX) {
    statusColor = "bg-queue-high text-queue-high-bg"
    borderColor = "border-queue-high/30"
    bgGradient = "from-queue-high/10 to-transparent"
  } else if (counter.queue_length > QUEUE_THRESHOLDS.LOW_MAX) {
    statusColor = "bg-queue-med text-queue-med-bg"
    borderColor = "border-queue-med/30"
    bgGradient = "from-queue-med/10 to-transparent"
  }

  // Handle manual increment/decrement
  const handleUpdate = async (delta: number) => {
    if (!onManualUpdate || isUpdating) return
    
    const newLength = Math.max(0, counter.queue_length + delta)
    if (newLength === counter.queue_length) return

    setIsUpdating(true)
    try {
      await onManualUpdate(counter.counter_id, newLength)
    } finally {
      setIsUpdating(false)
    }
  }

  // If counter is closed, render differently
  if (counter.status !== "open") {
    return (
      <div className="relative overflow-hidden rounded-xl border border-border bg-muted/30 p-5 opacity-70 grayscale transition-all hover:grayscale-0">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-semibold text-foreground">Counter #{counter.counter_number}</h3>
            <p className="text-xs text-muted-foreground">{counter.label || "Closed"}</p>
          </div>
          <span className="rounded-full bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
            {counter.status === "break" ? "On Break" : "Closed"}
          </span>
        </div>
        <div className="mt-8 flex items-center justify-center py-6">
          <p className="text-sm font-medium text-muted-foreground">Currently unavailable</p>
        </div>
      </div>
    )
  }

  return (
    <div 
      className={cn(
        "relative overflow-hidden rounded-xl border bg-card transition-all duration-300 hover:shadow-md",
        borderColor
      )}
    >
      {/* Subtle background gradient based on status */}
      <div className={cn("absolute inset-0 bg-gradient-to-br opacity-50", bgGradient)} />
      
      <div className="relative p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-foreground">Counter #{counter.counter_number}</h3>
              {/* Last updated indicator */}
              <div 
                className="group relative flex items-center justify-center"
                title={`Last updated: ${counter.last_updated ? new Date(counter.last_updated).toLocaleTimeString() : 'Unknown'}`}
              >
                <div className={cn("h-2 w-2 rounded-full", statusColor, "live-pulse")} />
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">{counter.label || "General Checkout"}</p>
          </div>
          
          <div className="flex items-center gap-1">
            <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wider", statusColor)}>
              {counter.status}
            </span>
          </div>
        </div>

        {/* Main metric display */}
        <div className="mt-6 flex items-end justify-between">
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
              <Users className="h-3 w-3" />
              Waiting
            </p>
            <div className="flex items-baseline gap-1">
              <span key={counter.queue_length} className="counter-flip text-4xl font-bold tracking-tight text-foreground">
                {counter.queue_length}
              </span>
              <span className="text-sm font-medium text-muted-foreground">ppl</span>
            </div>
          </div>
          
          <div className="text-right">
            <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center justify-end gap-1">
              <Clock className="h-3 w-3" />
              Est. Wait
            </p>
            <div className="flex items-baseline justify-end gap-1">
              <span key={counter.estimated_wait_seconds} className="counter-flip text-2xl font-bold tracking-tight text-foreground">
                {counter.estimated_wait_formatted.split(" ")[0]}
              </span>
              <span className="text-xs font-medium text-muted-foreground">
                {counter.estimated_wait_formatted.split(" ")[1]}
              </span>
            </div>
          </div>
        </div>

        {/* Manual controls override */}
        <div className="mt-6 flex items-center justify-between border-t border-border/50 pt-4">
          <div className="flex items-center gap-1.5">
            <Info className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground capitalize">
              Source: {counter.source || "Unknown"}
            </span>
          </div>
          
          {onManualUpdate && (
            <div className="flex items-center gap-2">
              <Button 
                variant="outline" 
                size="icon" 
                className="h-7 w-7 rounded-full"
                onClick={() => void handleUpdate(-1)}
                disabled={isUpdating || counter.queue_length === 0}
              >
                <Minus className="h-3 w-3" />
              </Button>
              <Button 
                variant="outline" 
                size="icon" 
                className="h-7 w-7 rounded-full"
                onClick={() => void handleUpdate(1)}
                disabled={isUpdating}
              >
                {isUpdating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
