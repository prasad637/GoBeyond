import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { LocationProvider } from "@/context/LocationContext";
import AppShell from "@/components/layout/AppShell";
import { cn } from "@/lib/cn";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-display",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "GO BEYOND — Discover. Book. Experience.",
  description: "All-in-one entertainment and lifestyle platform for Hyderabad: Movies, Dining, Live Events, Sports Turfs and Activities.",
  keywords: ["Hyderabad", "Movies", "Dining", "Restaurants", "Events", "Sports", "Activities", "Tickets", "Booking"],
  authors: [{ name: "GO BEYOND Platform Team" }],
  openGraph: {
    title: "GO BEYOND — Discover. Book. Experience.",
    description: "Premium entertainment and lifestyle ticketing for Hyderabad.",
    siteName: "GO BEYOND",
    locale: "en_IN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "GO BEYOND — Discover. Book. Experience.",
    description: "All-in-one entertainment, movie and event ticketing across Hyderabad.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={cn(
        "dark",
        plusJakartaSans.variable,
        inter.variable,
        jetbrainsMono.variable
      )}
    >
      <body className="min-h-screen flex flex-col bg-canvas text-primary font-sans antialiased">
        <AuthProvider>
          <LocationProvider>
            <AppShell>{children}</AppShell>
          </LocationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
