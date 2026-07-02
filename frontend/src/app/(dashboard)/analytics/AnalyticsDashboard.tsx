"use client"

import { useState } from "react"
import { BarChart3, Clock, Users, Calendar, TrendingUp, TrendingDown, Store } from "lucide-react"
import Link from "next/link"

import { useStoreSummary, usePeakHours, useQueueTrends } from "@/hooks/useAnalytics"
import { useStoreStore } from "@/store/storeStore"
import { TrendChart } from "@/components/analytics/TrendChart"
import { HeatmapChart } from "@/components/analytics/HeatmapChart"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/cn"

const TIMEFRAMES = [
  { id: 1, label: "Last 24h", bucket: 15 },
  { id: 7, label: "Last 7 Days", bucket: 60 },
  { id: 30, label: "Last 30 Days", bucket: 1440 },
]

export default function AnalyticsDashboard() {
  const { activeStoreId } = useStoreStore()
  // time frame is represented in days_back
  const [daysBack, setDaysBack] = useState(1)
  
  const currentTf = TIMEFRAMES.find(t => t.id === daysBack) || TIMEFRAMES[0]

  const { data: summaryRes, isLoading: isLoadingSummary } = useStoreSummary(daysBack)
  const { data: heatRes, isLoading: isLoadingHeat } = usePeakHours(Math.max(7, daysBack)) // min 7 days for heatmap
  const { data: trendRes, isLoading: isLoadingTrend } = useQueueTrends(daysBack, currentTf.bucket)

  if (!activeStoreId) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-24 text-center">
        <Store className="h-12 w-12 text-muted-foreground mb-4" />
        <h2 className="text-xl font-semibold">No Active Store</h2>
        <p className="text-muted-foreground mt-2 max-w-md">
          Select a store from the sidebar or stores page to view its analytics.
        </p>
        <Button asChild className="mt-6">
          <Link href="/stores">Go to Stores</Link>
        </Button>
      </div>
    )
  }

  const summary = summaryRes?.data
  const heatData = heatRes?.data?.cells || []
  const trendData = trendRes?.data?.buckets || []

  return (
    <div className="space-y-8 animate-fade-in pb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <BarChart3 className="h-7 w-7 text-primary" />
            Analytics & Insights
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Historical queue performance and predictive trends.
          </p>
        </div>
        
        {/* Timeframe Selector */}
        <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.id}
              onClick={() => setDaysBack(tf.id)}
              className={cn(
                "flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
                daysBack === tf.id
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Calendar className="h-4 w-4" />
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Total Customers (Est.)"
          icon={Users}
          value={summary ? summary.total_customers_estimated.toLocaleString() : undefined}
          isLoading={isLoadingSummary}
        />
        <KpiCard
          title="Avg Wait Time"
          icon={Clock}
          value={summary?.avg_wait_formatted}
          trendInverted
          isLoading={isLoadingSummary}
        />
        <KpiCard
          title="Peak Queue Length"
          icon={TrendingUp}
          value={summary ? summary.peak_queue_length.toString() : undefined}
          isLoading={isLoadingSummary}
        />
        <KpiCard
          title="Busiest Hour"
          icon={BarChart3}
          value={summary?.busiest_hour !== null && summary?.busiest_hour !== undefined ? `${summary.busiest_hour}:00` : "N/A"}
          isLoading={isLoadingSummary}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Trend Chart */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-card shadow-sm p-6 flex flex-col">
          <div className="mb-6">
            <h3 className="font-semibold text-lg">Queue Trends</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Wait times vs customer volume over time.
            </p>
          </div>
          <div className="flex-1 min-h-[300px]">
            <TrendChart data={trendData} isLoading={isLoadingTrend} />
          </div>
        </div>

        {/* Heatmap/Peak Hours */}
        <div className="rounded-xl border border-border bg-card shadow-sm p-6 flex flex-col">
          <div className="mb-6">
            <h3 className="font-semibold text-lg">Peak Hours</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Average wait times by hour of day.
            </p>
          </div>
          <div className="flex-1 min-h-[300px]">
            <HeatmapChart data={heatData} isLoading={isLoadingHeat} />
          </div>
        </div>
      </div>
    </div>
  )
}

function KpiCard({
  title,
  icon: Icon,
  value,
  trend,
  trendInverted = false,
  isLoading
}: {
  title: string
  icon: React.ElementType
  value?: string | undefined
  trend?: number | undefined
  trendInverted?: boolean | undefined
  isLoading?: boolean | undefined
}) {
  const isPositive = trend !== undefined && trend > 0;
  const isNegative = trend !== undefined && trend < 0;
  
  let trendColor = "text-muted-foreground";
  let TrendIcon = null;

  if (isPositive) {
    trendColor = trendInverted ? "text-destructive" : "text-success";
    TrendIcon = TrendingUp;
  } else if (isNegative) {
    trendColor = trendInverted ? "text-success" : "text-destructive";
    TrendIcon = TrendingDown;
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 text-muted-foreground mb-4">
        <Icon className="h-4 w-4" />
        <h3 className="text-sm font-medium">{title}</h3>
      </div>
      
      {isLoading ? (
        <Skeleton className="h-9 w-24" />
      ) : (
        <div className="flex items-end justify-between">
          <p className="text-3xl font-bold tracking-tight text-foreground">
            {value || "0"}
          </p>
          
          {trend !== undefined && TrendIcon && (
            <div className={cn("flex items-center gap-1 text-sm font-medium", trendColor)}>
              <TrendIcon className="h-4 w-4" />
              {Math.abs(trend)}%
            </div>
          )}
        </div>
      )}
    </div>
  )
}
