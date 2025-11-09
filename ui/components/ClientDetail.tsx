"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "./ui/button";
import { cn } from "@/utils/cn";

interface ClientHolding {
  holding_id: string;
  ticker: string;
  company_name: string;
  shares: number;
  cost_basis: number | null;
  purchase_date: string | null;
  notes: string | null;
  current_value: number | null;
}

interface Client {
  client_id: string;
  account_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  last_meeting_date: string | null;
  next_meeting_date: string | null;
  notes: string | null;
  client_metadata: Record<string, any>;
}

interface ClientDetailData {
  client: Client;
  holdings: ClientHolding[];
  total_holdings: number;
  advisor_name: string;
}

interface ClientDetailProps {
  accountId: string;
}

export function ClientDetail({ accountId }: ClientDetailProps) {
  const [data, setData] = useState<ClientDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchClientDetail = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          `http://localhost:8000/api/clients/${accountId}`
        );
        if (!response.ok) {
          throw new Error(`Failed to fetch client: ${response.statusText}`);
        }
        const clientData = await response.json();
        setData(clientData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchClientDetail();
  }, [accountId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Loading client details...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-destructive mb-4">
            {error || "Client not found"}
          </p>
          <Link href="/clients">
            <Button variant="outline">Back to Clients</Button>
          </Link>
        </div>
      </div>
    );
  }

  const { client, holdings, advisor_name } = data;

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "—";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  const formatCurrency = (value: number | null) => {
    if (value === null) return "—";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(value);
  };

  const calculateHoldingValue = (holding: ClientHolding) => {
    if (holding.cost_basis === null) return null;
    return holding.shares * holding.cost_basis;
  };

  const totalPortfolioValue = holdings.reduce((sum, holding) => {
    const value = calculateHoldingValue(holding);
    return value !== null ? sum + value : sum;
  }, 0);

  const getRiskBadgeColor = (riskTolerance: string) => {
    switch (riskTolerance?.toLowerCase()) {
      case "conservative":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
      case "moderate":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
      case "aggressive":
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    }
  };

  return (
    <div className="w-full max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link href="/clients">
          <Button variant="ghost" size="sm" className="mb-4">
            ← Back to Clients
          </Button>
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">
              {client.name}
            </h1>
            <p className="text-muted-foreground">
              Account ID: {client.account_id}
            </p>
          </div>
        </div>
      </div>

      {/* Client Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            Advisor
          </h3>
          <p className="text-lg font-semibold text-foreground">
            {advisor_name}
          </p>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            Risk Profile
          </h3>
          {client.client_metadata?.risk_tolerance ? (
            <span
              className={cn(
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium",
                getRiskBadgeColor(client.client_metadata.risk_tolerance)
              )}
            >
              {client.client_metadata.risk_tolerance}
            </span>
          ) : (
            <p className="text-foreground">—</p>
          )}
        </div>

        <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            Investment Goal
          </h3>
          <p className="text-lg font-semibold text-foreground capitalize">
            {client.client_metadata?.investment_goal || "—"}
          </p>
        </div>
      </div>

      {/* Contact & Meeting Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">
            Contact Information
          </h3>
          <div className="space-y-2">
            <div>
              <span className="text-xs text-muted-foreground">Email:</span>
              <p className="text-sm text-foreground">{client.email || "—"}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Phone:</span>
              <p className="text-sm text-foreground">{client.phone || "—"}</p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">
            Meeting Schedule
          </h3>
          <div className="space-y-2">
            <div>
              <span className="text-xs text-muted-foreground">
                Last Meeting:
              </span>
              <p className="text-sm text-foreground">
                {formatDate(client.last_meeting_date)}
              </p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">
                Next Meeting:
              </span>
              <p className="text-sm text-foreground font-medium">
                {formatDate(client.next_meeting_date)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Notes */}
      {client.notes && (
        <div className="rounded-lg border border-border bg-card p-4 shadow-sm mb-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            Notes
          </h3>
          <p className="text-sm text-foreground">{client.notes}</p>
        </div>
      )}

      {/* Portfolio Holdings */}
      <div className="rounded-lg border border-border bg-card shadow-sm">
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-foreground">
              Portfolio Holdings
            </h2>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">Total Value</p>
              <p className="text-2xl font-bold text-foreground">
                {formatCurrency(totalPortfolioValue)}
              </p>
            </div>
          </div>
        </div>

        {holdings.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            No holdings found for this client
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-border bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Ticker
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Company
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                    Shares
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                    Cost Basis
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                    Total Value
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Purchase Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {holdings.map((holding) => {
                  const totalValue = calculateHoldingValue(holding);
                  return (
                    <tr
                      key={holding.holding_id}
                      className="hover:bg-muted/50 transition-colors"
                    >
                      <td className="px-4 py-4">
                        <span className="font-mono font-semibold text-foreground">
                          {holding.ticker}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-sm text-foreground">
                        {holding.company_name}
                      </td>
                      <td className="px-4 py-4 text-right text-sm text-foreground">
                        {holding.shares.toLocaleString()}
                      </td>
                      <td className="px-4 py-4 text-right text-sm text-foreground">
                        {formatCurrency(holding.cost_basis)}
                      </td>
                      <td className="px-4 py-4 text-right text-sm font-semibold text-foreground">
                        {formatCurrency(totalValue)}
                      </td>
                      <td className="px-4 py-4 text-sm text-muted-foreground">
                        {formatDate(holding.purchase_date)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="p-4 border-t border-border bg-muted/20">
          <p className="text-sm text-muted-foreground">
            {holdings.length} position{holdings.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>
    </div>
  );
}
