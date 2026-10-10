import type { Metadata } from "next";
import { Archivo_Black, DM_Sans, Instrument_Serif } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const archivoBlack = Archivo_Black({
  variable: "--font-archivo-black",
  weight: "400",
  subsets: ["latin"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  display: "swap",
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  weight: "400",
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "AFTERMATH — Evidence-governed trading intelligence",
  description:
    "AFTERMATH connects market events, verifiable evidence, AI reasoning, deterministic risk controls, and auditable paper execution into one transparent workflow for tokenized US stocks.",
  keywords: [
    "AFTERMATH",
    "tokenized stocks",
    "evidence-governed trading",
    "AI risk controls",
    "paper execution",
    "auditable decisions",
  ],
  authors: [{ name: "AFTERMATH" }],
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    title: "AFTERMATH — Markets never sleep. Evidence should never be guessed.",
    description:
      "Evidence-governed AI trading intelligence for tokenized US stocks and perpetual markets.",
    siteName: "AFTERMATH",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${archivoBlack.variable} ${dmSans.variable} ${instrumentSerif.variable} font-sans antialiased bg-forest-deep text-ink`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
