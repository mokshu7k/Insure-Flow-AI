import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InsureFlow AI — Compliance-First Insurance Intelligence",
  description:
    "AI-powered insurance claim intelligence platform with fraud detection, cashless QR authorization, and full regulatory compliance.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
