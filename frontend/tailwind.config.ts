import type { Config } from "tailwindcss";

const config: Config = {
  // Enable dark mode via class strategy (controlled by next-themes)
  darkMode: ["class"],

  // Paths to all template files
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],

  theme: {
    extend: {
      // -------------------------------------------------------------------------
      // Design System — Color Tokens
      // Using HSL CSS variables for shadcn/ui compatibility
      // -------------------------------------------------------------------------
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",

        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },

        // RetailFlow AI — Brand Colors
        brand: {
          50: "hsl(224, 100%, 97%)",
          100: "hsl(224, 100%, 93%)",
          200: "hsl(224, 95%, 87%)",
          300: "hsl(224, 90%, 77%)",
          400: "hsl(224, 85%, 65%)",
          500: "hsl(224, 80%, 55%)", // Primary brand
          600: "hsl(224, 75%, 45%)",
          700: "hsl(224, 70%, 37%)",
          800: "hsl(224, 65%, 28%)",
          900: "hsl(224, 60%, 20%)",
          950: "hsl(224, 55%, 12%)",
        },

        // Queue Status Colors
        queue: {
          low: "hsl(142, 70%, 45%)",      // Green — 0–3 customers
          medium: "hsl(38, 92%, 50%)",    // Amber — 4–7 customers
          high: "hsl(0, 84%, 60%)",       // Red — 8+ customers
          "low-bg": "hsl(142, 70%, 95%)",
          "medium-bg": "hsl(38, 92%, 95%)",
          "high-bg": "hsl(0, 84%, 95%)",
        },
      },

      // -------------------------------------------------------------------------
      // Border Radius
      // -------------------------------------------------------------------------
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },

      // -------------------------------------------------------------------------
      // Typography
      // -------------------------------------------------------------------------
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },

      // -------------------------------------------------------------------------
      // Animations
      // -------------------------------------------------------------------------
      keyframes: {
        // shadcn/ui animations
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        // Custom RetailFlow animations
        "queue-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        "slide-in-from-right": {
          from: { transform: "translateX(100%)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "number-tick": {
          from: { transform: "translateY(-100%)" },
          to: { transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "badge-pop": {
          "0%": { transform: "scale(0.8)", opacity: "0" },
          "60%": { transform: "scale(1.1)" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "queue-pulse": "queue-pulse 2s ease-in-out infinite",
        "slide-in": "slide-in-from-right 0.3s ease-out",
        "fade-in": "fade-in 0.4s ease-out",
        "number-tick": "number-tick 0.3s ease-out",
        shimmer: "shimmer 2s infinite",
        "badge-pop": "badge-pop 0.3s ease-out",
      },

      // -------------------------------------------------------------------------
      // Shadows
      // -------------------------------------------------------------------------
      boxShadow: {
        "card-sm": "0 1px 3px 0 rgb(0 0 0 / 0.07), 0 1px 2px -1px rgb(0 0 0 / 0.07)",
        "card-md": "0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.07)",
        "card-lg": "0 10px 15px -3px rgb(0 0 0 / 0.07), 0 4px 6px -4px rgb(0 0 0 / 0.07)",
        glow: "0 0 20px rgb(59 130 246 / 0.35)",
        "glow-green": "0 0 20px rgb(34 197 94 / 0.35)",
        "glow-red": "0 0 20px rgb(239 68 68 / 0.35)",
      },
    },
  },

  plugins: [require("tailwindcss-animate")],
};

export default config;
