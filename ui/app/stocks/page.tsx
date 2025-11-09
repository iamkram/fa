import { StockSearch } from "@/components/StockSearch";

export default function StocksPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Stock Lookup
          </h1>
          <p className="text-muted-foreground">
            Search for stocks and view summaries and client ownership
          </p>
        </div>
        <div className="flex justify-center">
          <StockSearch />
        </div>
      </div>
    </div>
  );
}
