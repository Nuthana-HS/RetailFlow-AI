/**
 * RetailFlow AI — Stores Zustand Store
 *
 * Manages the current active store selection for the dashboard context.
 */
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface StoreState {
  activeStoreId: string | null;
  setActiveStoreId: (id: string | null) => void;
}

export const useStoreStore = create<StoreState>()(
  persist(
    (set) => ({
      activeStoreId: null,
      setActiveStoreId: (id) => set({ activeStoreId: id }),
    }),
    {
      name: "rf-store-storage", // stores activeStoreId in localStorage
      storage: createJSONStorage(() => localStorage),
    }
  )
);
