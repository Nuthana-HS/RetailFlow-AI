import type { Metadata } from "next";
import NewStoreForm from "./NewStoreForm";

export const metadata: Metadata = {
  title: "Add Store | RetailFlow AI",
};

export default function NewStorePage() {
  return <NewStoreForm />;
}
