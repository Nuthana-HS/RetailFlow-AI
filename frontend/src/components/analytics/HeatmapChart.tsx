"use client"

import { useMemo } from "react"
import { Bar } from "react-chartjs-2"
import type { TooltipItem } from "chart.js"
import { commonChartOptions } from "@/lib/chartSetup"
import type { HeatmapCell } from "@/types/analytics"
import { Skeleton } from "@/components/ui/skeleton"

interface HeatmapChartProps {
  data: HeatmapCell[]
  isLoading?: boolean
}

export function HeatmapChart({ data, isLoading }: HeatmapChartProps) {
  const chartData = useMemo(() => {
    // Sort by hour (0-23)
    const sortedData = [...data].sort((a, b) => a.hour_of_day - b.hour_of_day)

    return {
      labels: sortedData.map(d => `${d.hour_of_day}:00`),
      datasets: [
        {
          label: "Avg Queue Length",
          data: sortedData.map(d => d.avg_queue_length),
          backgroundColor: sortedData.map(d => {
            // Color intensity based on intensity (0.0 - 1.0)
            if (d.intensity > 0.7) return "hsl(var(--destructive))"
            if (d.intensity > 0.4) return "hsl(var(--warning))"
            return "hsl(var(--success))"
          }),
          borderRadius: 4,
          borderSkipped: false
        }
      ]
    }
  }, [data])

  const options = useMemo(() => ({
    ...commonChartOptions,
    plugins: {
      ...commonChartOptions.plugins,
      legend: {
        display: false // Hide legend for heatmap bar
      },
      tooltip: {
        ...commonChartOptions.plugins.tooltip,
        callbacks: {
          label: (context: TooltipItem<"bar">) => `Avg Queue Length: ${context.parsed.y}`
        }
      }
    },
    scales: {
      ...commonChartOptions.scales,
      x: {
        ...commonChartOptions.scales.x,
        title: {
          display: true,
          text: 'Hour of Day',
          color: 'hsl(var(--muted-foreground))'
        }
      },
      y: {
        ...commonChartOptions.scales.y,
        title: {
          display: true,
          text: 'Avg Queue Length',
          color: 'hsl(var(--muted-foreground))'
        }
      }
    }
  }), [])

  if (isLoading) {
    return <Skeleton className="h-full w-full rounded-xl" />
  }

  if (data.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No heatmap data available for this period.
      </div>
    )
  }

  return (
    <div className="h-full w-full min-h-[300px]">
      <Bar data={chartData} options={options} />
    </div>
  )
}
