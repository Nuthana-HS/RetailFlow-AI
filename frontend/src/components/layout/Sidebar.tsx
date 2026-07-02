"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BarChart3,
  Bell,
  LayoutDashboard,
  Settings,
  Store,
  ShoppingCart,
  BrainCircuit,
} from "lucide-react"

import { cn } from "@/lib/cn"

const NAV_ITEMS = [
  { name: "Live Queue", href: "/dashboard", icon: LayoutDashboard },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
  { name: "Stores", href: "/stores", icon: Store },
  { name: "ML Models", href: "/ml", icon: BrainCircuit },
  { name: "Notifications", href: "/notifications", icon: Bell },
  { name: "Settings", href: "/settings", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden w-64 flex-col border-r border-sidebar-border bg-sidebar md:flex">
      {/* Logo */}
      <div className="flex h-16 items-center px-6">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 ring-1 ring-primary/30">
            <ShoppingCart className="h-5 w-5 text-primary" />
          </div>
          <span className="text-lg font-bold tracking-tight text-sidebar-foreground">
            RetailFlow AI
          </span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1.5 px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-sidebar-accent text-sidebar-foreground shadow-sm"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
              )}
            >
              <item.icon
                className={cn(
                  "h-5 w-5",
                  isActive ? "text-sidebar-foreground" : "text-sidebar-foreground/50 group-hover:text-sidebar-foreground/70",
                )}
              />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Footer / Version */}
      <div className="border-t border-sidebar-border p-4">
        <div className="rounded-lg bg-sidebar-border/50 p-3 text-xs text-sidebar-foreground/60">
          <p className="font-semibold text-sidebar-foreground/80">RetailFlow AI</p>
          <p>Manager Dashboard v1.0</p>
        </div>
      </div>
    </aside>
  )
}
