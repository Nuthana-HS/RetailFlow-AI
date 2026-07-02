"use client"

import { useQuery } from "@tanstack/react-query"
import * as analyticsApi from "@/lib/api/analytics"
import { useStoreStore } from "@/store/storeStore"

export const ANALYTICS_QUERY_KEYS = {
  all: ["analytics"] as const,
  summary: (storeId: string | null, daysBack: number) => 
    [...ANALYTICS_QUERY_KEYS.all, "summary", storeId, daysBack] as const,
  peakHours: (storeId: string | null, daysBack: number) => 
    [...ANALYTICS_QUERY_KEYS.all, "peak-hours", storeId, daysBack] as const,
  trends: (storeId: string | null, daysBack: number, bucketMinutes: number) => 
    [...ANALYTICS_QUERY_KEYS.all, "trends", storeId, daysBack, bucketMinutes] as const,
}

export function useStoreSummary(daysBack: number = 1) {
  const { activeStoreId } = useStoreStore()
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.summary(activeStoreId, daysBack),
    queryFn: () => analyticsApi.getStoreSummary(activeStoreId!, daysBack),
    enabled: !!activeStoreId,
  })
}

export function usePeakHours(daysBack: number = 30) {
  const { activeStoreId } = useStoreStore()
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.peakHours(activeStoreId, daysBack),
    queryFn: () => analyticsApi.getPeakHours(activeStoreId!, daysBack),
    enabled: !!activeStoreId,
  })
}

export function useQueueTrends(daysBack: number = 1, bucketMinutes: number = 60) {
  const { activeStoreId } = useStoreStore()
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.trends(activeStoreId, daysBack, bucketMinutes),
    queryFn: () => analyticsApi.getQueueTrends(activeStoreId!, daysBack, bucketMinutes),
    enabled: !!activeStoreId,
  })
}
