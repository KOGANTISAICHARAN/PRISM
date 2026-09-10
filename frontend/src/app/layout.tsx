import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { BottomNav, ServiceWorkerRegistrar } from "@/components/Shell";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "PRISM — AI-powered food safety early warning",
  description:
    "Report. Detect. Investigate. Prevent. PRISM helps identify patterns in food-safety complaints and helps inspectors prioritise cases for investigation.",
  manifest: "/manifest.webmanifest",
  applicationName: "PRISM",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "PRISM" },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/icon-192.png", sizes: "192x192" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#2547eb",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} min-h-screen font-sans`}>
        <AuthProvider>
          <ServiceWorkerRegistrar />
          <div className="pb-20 md:pb-0">{children}</div>
          <BottomNav />
        </AuthProvider>
      </body>
    </html>
  );
}
