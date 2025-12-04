import type React from "react";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Movie Theater Agent Orchestration",
  description:
    "An intelligent platform for movie theater services, supporting ticket purchase, cancellation, seat reservations, exchanges, and detailed seat selections (window, center, VIP, accessible). Also provides support for technical issues, snacks, and movie/session information",
  icons: {
    icon: "/openai_logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body suppressHydrationWarning className={inter.className}>
        {children}
      </body>
    </html>
  );
}
