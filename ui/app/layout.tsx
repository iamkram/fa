import "./globals.css";
import { Inter } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import Image from "next/image";

const inter = Inter({ subsets: ["latin"] });

export const metadata = {
  title: "FA AI Assistant",
  description: "Professional AI assistant for financial advisors",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/images/compass-logo.png" />
      </head>
      <body className={inter.className}>
        <div className="bg-secondary grid grid-rows-[auto,1fr] h-[100dvh]">
          <div className="border-b border-input bg-background px-6 py-4">
            <div className="max-w-[1200px] mx-auto flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Image
                  src="/images/compass-logo.png"
                  alt="FA AI Assistant"
                  width={40}
                  height={40}
                  className="object-contain"
                />
                <div>
                  <h1 className="text-xl font-semibold text-foreground">
                    FA AI Assistant
                  </h1>
                  <p className="text-sm text-muted-foreground">
                    Professional insights for financial advisors
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div className="bg-background relative">
            <div className="absolute inset-0">{children}</div>
          </div>
        </div>
        <Toaster />
      </body>
    </html>
  );
}
