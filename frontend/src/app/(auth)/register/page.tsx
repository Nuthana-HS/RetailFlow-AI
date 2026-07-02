import type { Metadata } from "next";
import RegisterForm from "@/components/auth/RegisterForm";

export const metadata: Metadata = {
  title: "Create Account | RetailFlow AI",
  description: "Create your RetailFlow AI manager account.",
};

export default function RegisterPage() {
  return <RegisterForm />;
}
