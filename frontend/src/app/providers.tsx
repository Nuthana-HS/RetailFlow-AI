/**
 * RetailFlow AI — App Providers
 *
 * Client component wrapper for all context providers.
 * Separated from layout.tsx so the root layout stays a Server Component.
 */
"use client";

import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";

import { bootstrapApiClient } from "@/store/authStore";

// Create a stable QueryClient instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,          // 30s default
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

export function Providers({ children }: { children: React.ReactNode }) {
  // Wire Axios interceptors to the auth store on first client render
  useEffect(() => {
    bootstrapApiClient();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="dark"
        enableSystem
        disableTransitionOnChange
      >
        {children}
        <Toaster
          position="top-right"
          richColors
          closeButton
          toastOptions={{
            duration: 4000,
            classNames: {
              toast:
                "bg-card text-card-foreground border border-border shadow-lg font-sans text-sm",
            },
          }}
        />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
