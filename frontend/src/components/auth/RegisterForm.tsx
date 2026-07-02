"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Eye, EyeOff, ShoppingCart, Loader2 } from "lucide-react";
import { toast } from "sonner";

import * as authApi from "@/lib/api/auth";
import { useApiError } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";

// ─── Form Schema ─────────────────────────────────────────────────────────────
const registerSchema = z
  .object({
    full_name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Enter a valid email address"),
    role: z.enum(["manager", "admin", "customer"] as const),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/[A-Z]/, "Must contain at least one uppercase letter")
      .regex(/[0-9]/, "Must contain at least one number"),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

// ─── Component ───────────────────────────────────────────────────────────────
export default function RegisterForm() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [apiError, setApiError] = useState<unknown>(null);
  const errorMessage = useApiError(apiError);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { role: "manager" },
  });

  const onSubmit = async (values: RegisterFormValues) => {
    setApiError(null);
    try {
      await authApi.register({
        full_name: values.full_name,
        email: values.email,
        password: values.password,
        role: values.role,
      });
      toast.success("Account created! Please sign in.");
      router.push("/login");
    } catch (err: unknown) {
      setApiError(err);
    }
  };

  return (
    <div className="rounded-2xl border border-border/50 bg-card/90 backdrop-blur-sm p-8 shadow-2xl shadow-black/20">
      {/* Brand header */}
      <div className="mb-7 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 ring-1 ring-primary/20">
          <ShoppingCart className="h-7 w-7 text-primary" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Create account
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Get started with RetailFlow AI
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
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        {/* Full name */}
        <div className="space-y-1.5">
          <label htmlFor="reg-name" className="text-sm font-medium text-foreground">
            Full name
          </label>
          <input
            id="reg-name"
            type="text"
            autoComplete="name"
            placeholder="Jane Smith"
            className={cn(
              "w-full rounded-lg border bg-background px-3.5 py-2.5 text-sm placeholder:text-muted-foreground",
              "outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20",
              errors.full_name ? "border-destructive" : "border-input",
            )}
            {...register("full_name")}
          />
          {errors.full_name && (
            <p className="text-xs text-destructive">{errors.full_name.message}</p>
          )}
        </div>

        {/* Email */}
        <div className="space-y-1.5">
          <label htmlFor="reg-email" className="text-sm font-medium text-foreground">
            Email address
          </label>
          <input
            id="reg-email"
            type="email"
            autoComplete="email"
            placeholder="jane@yourstore.com"
            className={cn(
              "w-full rounded-lg border bg-background px-3.5 py-2.5 text-sm placeholder:text-muted-foreground",
              "outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20",
              errors.email ? "border-destructive" : "border-input",
            )}
            {...register("email")}
          />
          {errors.email && (
            <p className="text-xs text-destructive">{errors.email.message}</p>
          )}
        </div>

        {/* Role */}
        <div className="space-y-1.5">
          <label htmlFor="reg-role" className="text-sm font-medium text-foreground">
            Role
          </label>
          <select
            id="reg-role"
            className={cn(
              "w-full rounded-lg border bg-background px-3.5 py-2.5 text-sm",
              "outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20",
              "border-input",
            )}
            {...register("role")}
          >
            <option value="manager">Store Manager</option>
            <option value="admin">Administrator</option>
            <option value="customer">Customer</option>
          </select>
        </div>

        {/* Password */}
        <div className="space-y-1.5">
          <label htmlFor="reg-password" className="text-sm font-medium text-foreground">
            Password
          </label>
          <div className="relative">
            <input
              id="reg-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="••••••••"
              className={cn(
                "w-full rounded-lg border bg-background py-2.5 pl-3.5 pr-10 text-sm placeholder:text-muted-foreground",
                "outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20",
                errors.password ? "border-destructive" : "border-input",
              )}
              {...register("password")}
            />
            <button
              type="button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {errors.password && (
            <p className="text-xs text-destructive">{errors.password.message}</p>
          )}
        </div>

        {/* Confirm password */}
        <div className="space-y-1.5">
          <label htmlFor="reg-confirm" className="text-sm font-medium text-foreground">
            Confirm password
          </label>
          <div className="relative">
            <input
              id="reg-confirm"
              type={showConfirm ? "text" : "password"}
              autoComplete="new-password"
              placeholder="••••••••"
              className={cn(
                "w-full rounded-lg border bg-background py-2.5 pl-3.5 pr-10 text-sm placeholder:text-muted-foreground",
                "outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20",
                errors.confirm_password ? "border-destructive" : "border-input",
              )}
              {...register("confirm_password")}
            />
            <button
              type="button"
              aria-label={showConfirm ? "Hide password" : "Show password"}
              onClick={() => setShowConfirm((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {errors.confirm_password && (
            <p className="text-xs text-destructive">{errors.confirm_password.message}</p>
          )}
        </div>

        {/* Submit */}
        <button
          id="register-submit"
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
          {isSubmitting ? "Creating account…" : "Create account"}
        </button>
      </form>

      {/* Footer link */}
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
