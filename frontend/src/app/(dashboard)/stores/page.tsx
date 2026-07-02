import type { Metadata } from "next";
import StoresList from "./StoresList";

export const metadata: Metadata = {
  title: "Stores | RetailFlow AI",
  description: "Manage your retail locations and counters.",
};

export default function StoresPage() {
  return <StoresList />;
}
