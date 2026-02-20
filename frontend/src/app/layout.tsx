import type { Metadata } from "next";
import "./globals.css";
import { StoreHydrator } from "@/components/StoreHydrator";

export const metadata: Metadata = {
  title: "InsureFlow — Claim Intelligence Platform",
  description: "High-density claims processing, fraud intelligence, and compliance dashboard for insurance professionals.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body suppressHydrationWarning>
        <StoreHydrator />
        {children}
      </body>
    </html>
  );
}
