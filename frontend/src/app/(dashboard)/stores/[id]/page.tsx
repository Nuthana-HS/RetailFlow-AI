import type { Metadata } from "next";
import StoreDetail from "./StoreDetail";

export const metadata: Metadata = {
  title: "Store Details | RetailFlow AI",
};

export default function StoreDetailPage() {
  return <StoreDetail />;
}
