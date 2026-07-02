import type { Metadata } from "next";
import LoginForm from "@/components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Sign In | RetailFlow AI",
  description: "Sign in to your RetailFlow AI manager dashboard.",
};

export default function LoginPage() {
  return <LoginForm />;
}
