"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface SystemStatus {
  status: string;
  enabled: boolean;
  reason?: string;
  initiated_by?: string;
  initiated_at?: string;
  maintenance_message?: string;
  expected_restoration?: string;
}

export default function MaintenancePage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetchStatus();
    // Poll status every 10 seconds to check if maintenance is over
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${backendUrl}/admin/status`);
      const data = await response.json();
      setStatus(data);
      setLoading(false);

      // Check if this is a preview (has ?preview=true in URL)
      const urlParams = new URLSearchParams(window.location.search);
      const isPreview = urlParams.get('preview') === 'true';

      // If maintenance is over and not in preview mode, redirect to home
      if (data.status !== "maintenance" && !isPreview) {
        window.location.href = "/";
      }
    } catch (error) {
      console.error("Failed to fetch status:", error);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Check if this is a preview mode
  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const isPreview = urlParams?.get('preview') === 'true';

  return (
    <div className="flex items-center justify-center min-h-screen bg-background px-4 py-12">
      {isPreview && status?.status !== "maintenance" && (
        <div className="fixed top-0 left-0 right-0 bg-blue-600 text-white text-center py-2 text-sm font-medium z-50">
          Preview Mode - System is currently {status?.status?.toUpperCase()}
        </div>
      )}
      <div className="text-center max-w-2xl">
        {/* Icon */}
        <div className="mx-auto w-20 h-20 mb-6 rounded-full bg-yellow-100 flex items-center justify-center">
          <svg
            className="w-10 h-10 text-yellow-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        {/* Title */}
        <h1 className="text-4xl sm:text-5xl font-bold mb-4">
          System Under Maintenance
        </h1>

        {/* Custom Message or Default */}
        <div className="mb-8">
          {status?.maintenance_message ? (
            <p className="text-lg text-muted-foreground mb-4">
              {status.maintenance_message}
            </p>
          ) : (
            <p className="text-lg text-muted-foreground mb-4">
              The FA AI Assistant is currently undergoing maintenance.
              We'll be back online shortly.
            </p>
          )}

          {/* Reason (if available) */}
          {status?.reason && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
              <p className="text-sm font-medium text-yellow-900">
                Reason: {status.reason}
              </p>
            </div>
          )}

          {/* Expected Restoration Time */}
          {status?.expected_restoration && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-blue-900">
                <span className="font-medium">Expected restoration:</span>{" "}
                {new Date(status.expected_restoration).toLocaleString()}
              </p>
            </div>
          )}

          {/* Initiated Info */}
          {status?.initiated_at && (
            <p className="text-sm text-muted-foreground">
              Maintenance started {new Date(status.initiated_at).toLocaleString()}
            </p>
          )}
        </div>

        {/* Support Contact */}
        <div className="border-t pt-6">
          <p className="text-sm text-muted-foreground mb-2">
            For urgent inquiries, please contact:
          </p>
          <a
            href="mailto:support@example.com"
            className="text-sm font-medium text-primary hover:underline"
          >
            support@example.com
          </a>
        </div>

        {/* Admin Navigation */}
        <div className="border-t mt-6 pt-6">
          <p className="text-xs text-muted-foreground mb-3">Admin Access</p>
          <nav className="flex flex-wrap gap-2" aria-label="Admin navigation">
            <Link href="/">
              <Button variant="outline" size="sm">
                ← Home
              </Button>
            </Link>
            <Link href="/admin">
              <Button variant="outline" size="sm">
                Dashboard
              </Button>
            </Link>
            <Link href="/admin/load-test">
              <Button variant="outline" size="sm">
                Load Testing
              </Button>
            </Link>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open("http://localhost:8001/dashboard/", "_blank")}
            >
              Meta Monitoring
            </Button>
            <Button variant="default" size="sm" disabled>
              Maintenance Page
            </Button>
          </nav>
        </div>

        {/* Auto-refresh indicator */}
        <div className="mt-8 flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span>Checking for updates every 10 seconds...</span>
        </div>
      </div>
    </div>
  );
}
