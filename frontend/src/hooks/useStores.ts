"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import * as storesApi from "@/lib/api/stores"
import type {
  StoreCreateRequest,
  StoreUpdateRequest,
  CounterCreateRequest,
  CounterUpdateRequest,
} from "@/types/store"
import { getApiErrorMessage } from "@/lib/api/client"

export const STORES_QUERY_KEYS = {
  all: ["stores"] as const,
  lists: () => [...STORES_QUERY_KEYS.all, "list"] as const,
  list: (params: Record<string, unknown>) =>
    [...STORES_QUERY_KEYS.lists(), params] as const,
  details: () => [...STORES_QUERY_KEYS.all, "detail"] as const,
  detail: (id: string) => [...STORES_QUERY_KEYS.details(), id] as const,
}

// ─── Queries ─────────────────────────────────────────────────────────────────

export function useStores(params?: { page?: number; limit?: number; is_active?: boolean }) {
  return useQuery({
    queryKey: STORES_QUERY_KEYS.list(params ?? {}),
    queryFn: () => storesApi.getStores(params),
  })
}

export function useStore(id: string | null) {
  return useQuery({
    queryKey: STORES_QUERY_KEYS.detail(id!),
    queryFn: () => storesApi.getStore(id!),
    enabled: !!id,
  })
}

// ─── Mutations ───────────────────────────────────────────────────────────────

export function useCreateStore() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: StoreCreateRequest) => storesApi.createStore(data),
    onSuccess: () => {
      toast.success("Store created successfully")
      queryClient.invalidateQueries({ queryKey: STORES_QUERY_KEYS.lists() })
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error))
    },
  })
}

export function useUpdateStore() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: StoreUpdateRequest }) =>
      storesApi.updateStore(id, data),
    onSuccess: (res) => {
      toast.success("Store updated successfully")
      queryClient.invalidateQueries({ queryKey: STORES_QUERY_KEYS.detail(res.data.id) })
      queryClient.invalidateQueries({ queryKey: STORES_QUERY_KEYS.lists() })
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error))
    },
  })
}

export function useDeleteStore() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => storesApi.deleteStore(id),
    onSuccess: (_, id) => {
      toast.success("Store deleted successfully")
      queryClient.removeQueries({ queryKey: STORES_QUERY_KEYS.detail(id) })
      queryClient.invalidateQueries({ queryKey: STORES_QUERY_KEYS.lists() })
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error))
    },
  })
}

// ─── Counter Mutations ───────────────────────────────────────────────────────

export function useCreateCounter() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ storeId, data }: { storeId: string; data: CounterCreateRequest }) =>
      storesApi.createCounter(storeId, data),
    onSuccess: (_, variables) => {
      toast.success("Counter created successfully")
      queryClient.invalidateQueries({
        queryKey: STORES_QUERY_KEYS.detail(variables.storeId),
      })
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error))
    },
  })
}

export function useUpdateCounter() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      storeId,
      counterId,
      data,
    }: {
      storeId: string
      counterId: string
      data: CounterUpdateRequest
    }) => storesApi.updateCounter(storeId, counterId, data),
    onSuccess: (_, variables) => {
      toast.success("Counter updated successfully")
      queryClient.invalidateQueries({
        queryKey: STORES_QUERY_KEYS.detail(variables.storeId),
      })
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error))
    },
  })
}

export function useDeleteCounter() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ storeId, counterId }: { storeId: string; counterId: string }) =>
      storesApi.deleteCounter(storeId, counterId),
    onSuccess: (_, variables) => {
      toast.success("Counter deleted successfully")
      queryClient.invalidateQueries({
        queryKey: STORES_QUERY_KEYS.detail(variables.storeId),
      })
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error))
    },
  })
}
