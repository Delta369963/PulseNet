import type { Metadata } from "next";
import { Geist, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Toaster as SonnerToaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PulseNet — Predictive Decision-Support for Critical Resource Shortages",
  description:
    "PulseNet fuses live shock signals with a public trade dependency graph to predict where the next shortage of LPG, fuel, medicine, or wheat will hit — and hands a human administrator a one-click way to stop it. Decision-support only. Human-in-the-loop.",
  keywords: [
    "PulseNet",
    "supply chain",
    "critical resources",
    "shortage prediction",
    "decision support",
    "LPG",
    "fuel",
    "wheat",
    "human-in-the-loop",
  ],
  authors: [{ name: "PulseNet" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${jetbrainsMono.variable} antialiased bg-background text-foreground`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          {children}
          <SonnerToaster position="bottom-right" richColors closeButton />
        </ThemeProvider>
      </body>
    </html>
  );
}
