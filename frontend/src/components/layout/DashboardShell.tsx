"use client"

import { Sidebar } from "./Sidebar"
import { Topbar } from "./Topbar"

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen w-full bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl h-full animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
