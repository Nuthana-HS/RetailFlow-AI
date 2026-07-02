"use client";

import { useState } from "react";
import Link from "next/link";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Eye, EyeOff, ShoppingCart, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useAuth, useApiError } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";

// ─── Form Schema ─────────────────────────────────────────────────────────────
const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

// ─── Component ───────────────────────────────────────────────────────────────
export default function LoginForm() {
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [apiError, setApiError] = useState<unknown>(null);
  const errorMessage = useApiError(apiError);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (values: LoginFormValues) => {
    setApiError(null);
    try {
      await login(values.email, values.password);
      toast.success("Welcome back!");
    } catch (err: unknown) {
      setApiError(err);
    }
  };

  return (
    <div className="rounded-2xl border border-border/50 bg-card/90 backdrop-blur-sm p-8 shadow-2xl shadow-black/20">
      {/* Brand header */}
      <div className="mb-8 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 ring-1 ring-primary/20">
          <ShoppingCart className="h-7 w-7 text-primary" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          RetailFlow AI
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Sign in to your manager dashboard
        </p>
      </div>

      {/* Error banner */}
      {errorMessage && (
        <div
          role="alert"
          className="mb-5 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {errorMessage}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
        {/* Email */}
        <div className="space-y-1.5">
          <label
            htmlFor="login-email"
            className="text-sm font-medium text-foreground"
          >
            Email address
          </label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="manager@yourstore.com"
            className={cn(
              "w-full rounded-lg border bg-background px-3.5 py-2.5 text-sm placeholder:text-muted-foreground",
              "outline-none ring-offset-background transition-colors",
              "focus:border-primary focus:ring-2 focus:ring-primary/20",
              errors.email
                ? "border-destructive focus:border-destructive focus:ring-destructive/20"
                : "border-input",
            )}
            {...register("email")}
          />
          {errors.email && (
            <p className="text-xs text-destructive">{errors.email.message}</p>
          )}
        </div>

        {/* Password */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="login-password"
              className="text-sm font-medium text-foreground"
            >
              Password
            </label>
          </div>
          <div className="relative">
            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="••••••••"
              className={cn(
                "w-full rounded-lg border bg-background py-2.5 pl-3.5 pr-10 text-sm placeholder:text-muted-foreground",
                "outline-none ring-offset-background transition-colors",
                "focus:border-primary focus:ring-2 focus:ring-primary/20",
                errors.password
                  ? "border-destructive focus:border-destructive focus:ring-destructive/20"
                  : "border-input",
              )}
              {...register("password")}
            />
            <button
              type="button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
          {errors.password && (
            <p className="text-xs text-destructive">{errors.password.message}</p>
          )}
        </div>

        {/* Submit */}
        <button
          id="login-submit"
          type="submit"
          disabled={isSubmitting}
          className={cn(
            "w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground",
            "transition-all duration-200 hover:bg-primary/90 hover:shadow-md hover:shadow-primary/25",
            "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
            "disabled:cursor-not-allowed disabled:opacity-60",
            "flex items-center justify-center gap-2",
          )}
        >
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {/* Footer link */}
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link
          href="/register"
          className="font-medium text-primary hover:underline"
        >
          Create account
        </Link>
      </p>
    </div>
  );
}
