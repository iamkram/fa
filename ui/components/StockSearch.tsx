"use client";

import { useState, useEffect, useCallback } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useRouter } from "next/navigation";
import { debounce } from "lodash";

interface Stock {
  stock_id: string;
  ticker: string;
  company_name: string;
  cusip: string | null;
  sector: string | null;
}

export function StockSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Stock[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const router = useRouter();

  const searchStocks = useCallback(
    debounce(async (searchQuery: string) => {
      if (searchQuery.length < 1) {
        setResults([]);
        setShowResults(false);
        return;
      }

      setIsLoading(true);
      try {
        const response = await fetch(
          `http://localhost:8000/api/stocks/search?q=${encodeURIComponent(
            searchQuery
          )}`
        );
        if (response.ok) {
          const data = await response.json();
          setResults(data);
          setShowResults(true);
        }
      } catch (error) {
        console.error("Error searching stocks:", error);
      } finally {
        setIsLoading(false);
      }
    }, 300),
    []
  );

  useEffect(() => {
    searchStocks(query);
  }, [query, searchStocks]);

  const handleStockClick = (ticker: string) => {
    router.push(`/stocks/${ticker}`);
    setShowResults(false);
    setQuery("");
  };

  return (
    <div className="relative w-full max-w-2xl">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search stocks by ticker or company name (e.g., AAPL, Apple)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query && setShowResults(true)}
          onBlur={() => setTimeout(() => setShowResults(false), 200)}
          className="pl-10 pr-4 h-12 text-base"
        />
      </div>

      {showResults && results.length > 0 && (
        <Card className="absolute z-50 w-full mt-2 max-h-96 overflow-auto shadow-lg">
          <div className="p-2">
            {results.map((stock) => (
              <button
                key={stock.stock_id}
                onClick={() => handleStockClick(stock.ticker)}
                className="w-full text-left px-4 py-3 hover:bg-accent rounded-md transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-foreground">
                      {stock.ticker}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {stock.company_name}
                    </div>
                  </div>
                  {stock.sector && (
                    <div className="text-xs text-muted-foreground bg-secondary px-2 py-1 rounded">
                      {stock.sector}
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        </Card>
      )}

      {showResults && query && results.length === 0 && !isLoading && (
        <Card className="absolute z-50 w-full mt-2 p-4 shadow-lg">
          <p className="text-sm text-muted-foreground">No stocks found</p>
        </Card>
      )}
    </div>
  );
}
