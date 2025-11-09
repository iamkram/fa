import { StockDetail } from "@/components/StockDetail";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

export default function StockDetailPage({
  params,
}: {
  params: { ticker: string };
}) {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <Link
          href="/stocks"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to Stock Search
        </Link>
        <StockDetail ticker={params.ticker.toUpperCase()} />
      </div>
    </div>
  );
}
