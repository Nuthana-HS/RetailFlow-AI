"use client"

import { useMemo } from "react"
import { Line } from "react-chartjs-2"
import { commonChartOptions } from "@/lib/chartSetup"
import type { TrendBucket } from "@/types/analytics"
import { Skeleton } from "@/components/ui/skeleton"

interface TrendChartProps {
  data: TrendBucket[]
  isLoading?: boolean
}

export function TrendChart({ data, isLoading }: TrendChartProps) {
  const chartData = useMemo(() => {
    return {
      labels: data.map(d => {
        // Format timestamp for display (e.g., "10:00" or "Mon")
        const date = new Date(d.bucket_time)
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }),
      datasets: [
        {
          label: "Avg Queue Length",
          data: data.map(d => d.avg_queue_length),
          borderColor: "hsl(var(--primary))",
          backgroundColor: "hsl(var(--primary) / 0.1)",
          borderWidth: 2,
          pointBackgroundColor: "hsl(var(--primary))",
          pointBorderColor: "hsl(var(--background))",
          pointHoverBackgroundColor: "hsl(var(--primary))",
          pointHoverBorderColor: "hsl(var(--background))",
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: true,
          tension: 0.4 // Smooth curves
        },
        {
          label: "Max Queue Length",
          data: data.map(d => d.max_queue_length),
          borderColor: "hsl(var(--muted-foreground) / 0.5)",
          borderWidth: 2,
          borderDash: [5, 5], // Dashed line
          pointRadius: 0,
          fill: false,
          tension: 0.4
        }
      ]
    }
  }, [data])

  if (isLoading) {
    return <Skeleton className="h-full w-full rounded-xl" />
  }

  if (data.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No trend data available for this period.
      </div>
    )
  }

  return (
    <div className="h-full w-full min-h-[300px]">
      <Line data={chartData} options={commonChartOptions} />
    </div>
  )
}
