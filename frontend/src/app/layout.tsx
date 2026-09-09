import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { Shield } from "lucide-react";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SupplyChain Sentinel",
  description: "Autonomous Supply Chain Disruption Management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-[#FAFAFA] text-[#1A1F2C] min-h-screen flex flex-col`}>
        <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 text-blue-900 hover:text-blue-800 transition-colors">
              <Shield className="w-6 h-6 text-blue-900" />
              <span className="font-bold text-lg tracking-tight">SupplyChain Sentinel</span>
            </Link>
            <nav className="flex items-center gap-6 text-sm font-medium">
              <Link href="/" className="text-gray-600 hover:text-blue-900">Dashboard</Link>
              <Link href="/approvals" className="text-gray-600 hover:text-blue-900">Approvals Queue</Link>
            </nav>
          </div>
        </header>
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
