"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "./ui/button";
import { cn } from "@/utils/cn";

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

interface ClientListProps {
  advisorId?: string;
}

export function ClientList({ advisorId = "FA-001" }: ClientListProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchClients = async () => {
      try {
        setLoading(true);
        const url = advisorId
          ? `http://localhost:8000/api/clients?advisor_id=${advisorId}`
          : "http://localhost:8000/api/clients";

        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to fetch clients: ${response.statusText}`);
        }
        const data = await response.json();
        setClients(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchClients();
  }, [advisorId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Loading clients...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Error: {error}</p>
      </div>
    );
  }

  if (clients.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">No clients found</p>
      </div>
    );
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "—";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

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
    <div className="w-full">
      <div className="rounded-lg border border-border bg-card shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-border bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Client
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Contact
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Risk Profile
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Next Meeting
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {clients.map((client) => (
                <tr
                  key={client.client_id}
                  className="hover:bg-muted/50 transition-colors"
                >
                  <td className="px-4 py-4">
                    <div>
                      <Link
                        href={`/clients/${client.account_id}`}
                        className="font-medium text-foreground hover:text-primary hover:underline"
                      >
                        {client.name}
                      </Link>
                      <div className="text-xs text-muted-foreground">
                        {client.account_id}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="text-sm">
                      {client.email && (
                        <div className="text-foreground">{client.email}</div>
                      )}
                      {client.phone && (
                        <div className="text-muted-foreground text-xs">
                          {client.phone}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    {client.client_metadata?.risk_tolerance && (
                      <span
                        className={cn(
                          "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                          getRiskBadgeColor(client.client_metadata.risk_tolerance)
                        )}
                      >
                        {client.client_metadata.risk_tolerance}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-sm text-foreground">
                    {formatDate(client.next_meeting_date)}
                  </td>
                  <td className="px-4 py-4 text-right">
                    <Link href={`/clients/${client.account_id}`}>
                      <Button variant="outline" size="sm">
                        View Details
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="mt-4 text-sm text-muted-foreground">
        Showing {clients.length} client{clients.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}
