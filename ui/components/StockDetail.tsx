"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Building2, Calendar, Users, TrendingUp } from "lucide-react";
import Link from "next/link";
import { SummaryHistory } from "@/components/SummaryHistory";

interface Stock {
  stock_id: string;
  ticker: string;
  company_name: string;
  cusip: string | null;
  sector: string | null;
}

interface StockSummary {
  summary_id: string;
  summary_text: string;
  generation_date: string;
}

interface Owner {
  client_id: string;
  account_id: string;
  client_name: string;
  shares: number;
  cost_basis: number | null;
  total_value: number | null;
}

interface StockDetailData {
  stock: Stock;
  recent_summary: StockSummary | null;
  owners: Owner[];
  total_owners: number;
  total_shares_held: number;
}

interface StockDetailProps {
  ticker: string;
}

export function StockDetail({ ticker }: StockDetailProps) {
  const [stockData, setStockData] = useState<StockDetailData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStockDetail = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `http://localhost:8000/api/stocks/${ticker}`
        );

        if (!response.ok) {
          throw new Error("Stock not found");
        }

        const data = await response.json();
        setStockData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load stock");
      } finally {
        setIsLoading(false);
      }
    };

    fetchStockDetail();
  }, [ticker]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error || !stockData) {
    return (
      <Card>
        <CardContent className="py-12">
          <p className="text-center text-muted-foreground">
            {error || "Stock not found"}
          </p>
        </CardContent>
      </Card>
    );
  }

  const { stock, recent_summary, owners, total_owners, total_shares_held } =
    stockData;

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(value);
  };

  return (
    <div className="space-y-6">
      {/* Stock Header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-3xl">{stock.ticker}</CardTitle>
              <p className="text-xl text-muted-foreground mt-1">
                {stock.company_name}
              </p>
            </div>
            {stock.sector && (
              <Badge variant="secondary" className="text-sm">
                {stock.sector}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {stock.cusip && (
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">CUSIP</p>
                  <p className="font-mono text-sm">{stock.cusip}</p>
                </div>
              </div>
            )}
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Total Owners</p>
                <p className="font-semibold">{total_owners}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">
                  Total Shares Held
                </p>
                <p className="font-semibold">
                  {total_shares_held.toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Summary */}
      {recent_summary && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Recent Summary</CardTitle>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Calendar className="h-4 w-4" />
                {formatDate(recent_summary.generation_date)}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {recent_summary.summary_text}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Client Ownership */}
      <Card>
        <CardHeader>
          <CardTitle>Client Ownership</CardTitle>
          <p className="text-sm text-muted-foreground">
            Clients in your book who hold {stock.ticker}
          </p>
        </CardHeader>
        <CardContent>
          {owners.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No clients currently hold this stock
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b">
                  <tr>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      Client
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      Account
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                      Shares
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                      Cost Basis
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                      Total Value
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {owners.map((owner) => (
                    <tr
                      key={owner.client_id}
                      className="hover:bg-accent transition-colors"
                    >
                      <td className="py-3 px-4">
                        <Link
                          href={`/clients/${owner.account_id}`}
                          className="font-medium text-foreground hover:underline"
                        >
                          {owner.client_name}
                        </Link>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-muted-foreground font-mono">
                          {owner.account_id}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-sm">
                        {owner.shares.toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-sm">
                        {owner.cost_basis
                          ? formatCurrency(owner.cost_basis)
                          : "—"}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-sm font-semibold">
                        {owner.total_value
                          ? formatCurrency(owner.total_value)
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary History & Comparison */}
      <SummaryHistory ticker={stock.ticker} />
    </div>
  );
}
