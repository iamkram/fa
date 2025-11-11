"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
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

export default function AdminPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [killSwitchForm, setKillSwitchForm] = useState({
    reason: "",
    message: "",
    expectedRestoration: "",
  });
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingAction, setPendingAction] = useState<"activate" | "deactivate" | null>(null);
  const reasonInputRef = useRef<HTMLInputElement | null>(null);

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetchStatus();
    // Poll status every 10 seconds
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // ⌘R or Ctrl+R to refresh status
      if ((e.metaKey || e.ctrlKey) && e.key === 'r') {
        e.preventDefault();
        fetchStatus();
        toast.success("Status refreshed", {
          description: "System status has been updated with the latest information.",
        });
      }

      // ⌘M or Ctrl+M to focus reason field
      if ((e.metaKey || e.ctrlKey) && e.key === 'm') {
        e.preventDefault();
        reasonInputRef.current?.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${backendUrl}/admin/status`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error("Failed to fetch status:", error);
    }
  };

  const confirmToggleKillSwitch = (enabled: boolean) => {
    if (!killSwitchForm.reason.trim()) {
      toast.error("Please provide a reason");
      return;
    }
    setPendingAction(enabled ? "activate" : "deactivate");
    setShowConfirmDialog(true);
  };

  const toggleKillSwitch = async () => {
    const enabled = pendingAction === "activate";
    setShowConfirmDialog(false);
    setLoading(true);

    try {
      const response = await fetch(`${backendUrl}/admin/kill-switch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled,
          reason: killSwitchForm.reason,
          initiated_by: "admin-ui",
          message: killSwitchForm.message || undefined,
          expected_restoration: killSwitchForm.expectedRestoration || undefined,
        }),
      });

      if (!response.ok) throw new Error("Failed to toggle kill switch");

      const data = await response.json();
      setStatus(data.status);

      if (enabled) {
        toast.success("Maintenance mode activated", {
          description: `Reason: ${killSwitchForm.reason}. Users will see the maintenance page.`,
          action: {
            label: "View Maintenance Page",
            onClick: () => window.open("/maintenance?preview=true", "_blank"),
          },
        });
      } else {
        toast.success("System reactivated successfully", {
          description: "All services are now operational. Users can access the system.",
          action: {
            label: "View System Status",
            onClick: () => fetchStatus(),
          },
        });
      }

      // Clear form
      setKillSwitchForm({ reason: "", message: "", expectedRestoration: "" });

      // Refresh status
      await fetchStatus();
    } catch (error: any) {
      toast.error("Failed to toggle kill switch", {
        description: error.message || "Unable to connect to the backend. Please check that the server is running.",
        action: {
          label: "Retry",
          onClick: () => toggleKillSwitch(),
        },
      });
    } finally {
      setLoading(false);
      setPendingAction(null);
    }
  };

  const isInMaintenance = status?.status === "maintenance";

  return (
    <div className="container mx-auto p-4 sm:p-6 md:p-8 max-w-4xl">
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold mb-4">System Administration</h1>

        {/* Navigation */}
        <nav className="flex flex-wrap gap-2" aria-label="Admin navigation">
          <Link href="/">
            <Button variant="outline" size="sm">
              ← Home
            </Button>
          </Link>
          <Button variant="default" size="sm" disabled>
            Dashboard
          </Button>
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
          <Link href="/maintenance?preview=true">
            <Button variant="outline" size="sm">
              Maintenance Page
            </Button>
          </Link>
        </nav>
      </div>

      {/* Current Status */}
      <div className="bg-card border rounded-lg p-4 sm:p-6 mb-6 sm:mb-8" role="region" aria-labelledby="system-status-heading">
        <h2 id="system-status-heading" className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Current System Status</h2>
        {status ? (
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Status:</span>
              <span
                className={`px-3 py-1 rounded-full text-sm font-semibold ${
                  isInMaintenance
                    ? "bg-red-100 text-red-800 animate-pulse"
                    : "bg-green-100 text-green-800"
                }`}
              >
                {status.status.toUpperCase()}
              </span>
            </div>
            {status.reason && (
              <p className="text-sm text-muted-foreground">
                <strong>Reason:</strong> {status.reason}
              </p>
            )}
            {status.initiated_by && (
              <p className="text-sm text-muted-foreground">
                <strong>By:</strong> {status.initiated_by}
              </p>
            )}
            {status.initiated_at && (
              <p className="text-sm text-muted-foreground">
                <strong>At:</strong>{" "}
                {new Date(status.initiated_at).toLocaleString()}
              </p>
            )}
            {status.maintenance_message && (
              <p className="text-sm text-muted-foreground">
                <strong>Message:</strong> {status.maintenance_message}
              </p>
            )}
            {status.expected_restoration && (
              <p className="text-sm text-muted-foreground">
                <strong>Expected Restoration:</strong>{" "}
                {new Date(status.expected_restoration).toLocaleString()}
              </p>
            )}
          </div>
        ) : (
          <p className="text-muted-foreground">Loading...</p>
        )}
      </div>

      {/* Kill Switch Control */}
      <div className="bg-card border rounded-lg p-4 sm:p-6 mb-6 sm:mb-8">
        <h2 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Kill Switch</h2>

        <div className="space-y-4 mb-6" role="form" aria-label="Kill switch configuration">
          <div>
            <label htmlFor="kill-switch-reason" className="block text-sm font-medium mb-2">
              Reason <span className="text-red-500" aria-label="required">*</span>
            </label>
            <Input
              id="kill-switch-reason"
              ref={reasonInputRef}
              value={killSwitchForm.reason}
              onChange={(e) =>
                setKillSwitchForm({ ...killSwitchForm, reason: e.target.value })
              }
              placeholder="e.g., Emergency database maintenance"
              disabled={loading}
              aria-required="true"
              aria-label="Reason for maintenance mode"
            />
          </div>

          <div>
            <label htmlFor="kill-switch-message" className="block text-sm font-medium mb-2">
              User Message (Optional)
            </label>
            <Textarea
              id="kill-switch-message"
              value={killSwitchForm.message}
              onChange={(e) =>
                setKillSwitchForm({ ...killSwitchForm, message: e.target.value })
              }
              placeholder="Message to display to users"
              disabled={loading}
              aria-label="Custom message to display on maintenance page"
            />
          </div>

          <div>
            <label htmlFor="kill-switch-restoration" className="block text-sm font-medium mb-2">
              Expected Restoration (Optional)
            </label>
            <Input
              id="kill-switch-restoration"
              type="datetime-local"
              value={killSwitchForm.expectedRestoration}
              onChange={(e) =>
                setKillSwitchForm({
                  ...killSwitchForm,
                  expectedRestoration: e.target.value,
                })
              }
              disabled={loading}
              aria-label="Expected system restoration time"
            />
          </div>
        </div>

        <div className="flex gap-4">
          {!isInMaintenance ? (
            <Button
              onClick={() => confirmToggleKillSwitch(true)}
              disabled={loading}
              variant="destructive"
              className="flex-1"
              aria-label="Activate maintenance mode and prevent user access"
              aria-describedby="maintenance-help-text"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  Activating...
                </>
              ) : (
                "Activate Maintenance Mode"
              )}
            </Button>
          ) : (
            <Button
              onClick={() => confirmToggleKillSwitch(false)}
              disabled={loading}
              className="flex-1 bg-green-600 hover:bg-green-700"
              aria-label="Reactivate system and restore user access"
              aria-describedby="maintenance-help-text"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  Reactivating...
                </>
              ) : (
                "Reactivate System"
              )}
            </Button>
          )}
        </div>

        <p id="maintenance-help-text" className="text-sm text-muted-foreground mt-4">
          {isInMaintenance
            ? "System is currently in maintenance mode. Click above to restore service."
            : "Activating maintenance mode will prevent all user queries and display a maintenance page."}
        </p>
      </div>

      {/* LangSmith Monitoring Section */}
      <div className="bg-card border rounded-lg p-4 sm:p-6">
        <h2 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">LangSmith Monitoring</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Project</label>
            <p className="text-sm bg-secondary px-3 py-2 rounded">
              {process.env.NEXT_PUBLIC_LANGSMITH_PROJECT || "fa-ai-dev"}
            </p>
          </div>

          <div className="flex gap-4">
            <Button
              onClick={() => window.open("https://smith.langchain.com", "_blank")}
              variant="outline"
              className="flex-1"
            >
              Open LangSmith Dashboard
            </Button>
          </div>

          <p className="text-sm text-muted-foreground">
            All system actions and queries are automatically traced to LangSmith.
            View detailed traces, performance metrics, and error analysis in the dashboard.
          </p>
        </div>
      </div>

      {/* Confirmation Dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pendingAction === "activate"
                ? "Activate Maintenance Mode?"
                : "Reactivate System?"}
            </DialogTitle>
            <DialogDescription>
              {pendingAction === "activate" ? (
                <>
                  This will immediately put the system into maintenance mode.
                  All user queries will be blocked and users will see a
                  maintenance page.
                  <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm">
                    <p className="font-semibold text-yellow-900">
                      Reason: {killSwitchForm.reason}
                    </p>
                    {killSwitchForm.message && (
                      <p className="text-yellow-800 mt-1">
                        Message: {killSwitchForm.message}
                      </p>
                    )}
                    {killSwitchForm.expectedRestoration && (
                      <p className="text-yellow-800 mt-1">
                        Expected restoration:{" "}
                        {new Date(
                          killSwitchForm.expectedRestoration
                        ).toLocaleString()}
                      </p>
                    )}
                  </div>
                </>
              ) : (
                <>
                  This will reactivate the system and restore normal operations.
                  Users will be able to submit queries again.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowConfirmDialog(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button
              variant={pendingAction === "activate" ? "destructive" : "default"}
              onClick={toggleKillSwitch}
              disabled={loading}
              className={
                pendingAction === "deactivate"
                  ? "bg-green-600 hover:bg-green-700"
                  : ""
              }
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {pendingAction === "activate"
                    ? "Activating..."
                    : "Reactivating..."}
                </>
              ) : pendingAction === "activate" ? (
                "Yes, Activate Maintenance Mode"
              ) : (
                "Yes, Reactivate System"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
