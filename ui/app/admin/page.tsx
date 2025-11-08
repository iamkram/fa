"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

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

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetchStatus();
    // Poll status every 10 seconds
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
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

  const toggleKillSwitch = async (enabled: boolean) => {
    if (!killSwitchForm.reason.trim()) {
      toast.error("Please provide a reason");
      return;
    }

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

      toast.success(
        enabled ? "Maintenance mode activated" : "System reactivated"
      );

      // Clear form
      setKillSwitchForm({ reason: "", message: "", expectedRestoration: "" });

      // Refresh status
      await fetchStatus();
    } catch (error: any) {
      toast.error(error.message || "Failed to toggle kill switch");
    } finally {
      setLoading(false);
    }
  };

  const isInMaintenance = status?.status === "maintenance";

  return (
    <div className="container mx-auto p-8 max-w-4xl">
      <h1 className="text-3xl font-bold mb-8">System Administration</h1>

      {/* Current Status */}
      <div className="bg-card border rounded-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Current System Status</h2>
        {status ? (
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Status:</span>
              <span
                className={`px-3 py-1 rounded-full text-sm font-semibold ${
                  isInMaintenance
                    ? "bg-red-100 text-red-800"
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
      <div className="bg-card border rounded-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Kill Switch</h2>

        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-sm font-medium mb-2">
              Reason <span className="text-red-500">*</span>
            </label>
            <Input
              value={killSwitchForm.reason}
              onChange={(e) =>
                setKillSwitchForm({ ...killSwitchForm, reason: e.target.value })
              }
              placeholder="e.g., Emergency database maintenance"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              User Message (Optional)
            </label>
            <Textarea
              value={killSwitchForm.message}
              onChange={(e) =>
                setKillSwitchForm({ ...killSwitchForm, message: e.target.value })
              }
              placeholder="Message to display to users"
              disabled={loading}
              rows={3}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Expected Restoration (Optional)
            </label>
            <Input
              type="datetime-local"
              value={killSwitchForm.expectedRestoration}
              onChange={(e) =>
                setKillSwitchForm({
                  ...killSwitchForm,
                  expectedRestoration: e.target.value,
                })
              }
              disabled={loading}
            />
          </div>
        </div>

        <div className="flex gap-4">
          {!isInMaintenance ? (
            <Button
              onClick={() => toggleKillSwitch(true)}
              disabled={loading}
              variant="destructive"
              className="flex-1"
            >
              {loading ? "Activating..." : "Activate Maintenance Mode"}
            </Button>
          ) : (
            <Button
              onClick={() => toggleKillSwitch(false)}
              disabled={loading}
              className="flex-1 bg-green-600 hover:bg-green-700"
            >
              {loading ? "Reactivating..." : "Reactivate System"}
            </Button>
          )}
        </div>

        <p className="text-sm text-muted-foreground mt-4">
          {isInMaintenance
            ? "System is currently in maintenance mode. Click above to restore service."
            : "Activating maintenance mode will prevent all user queries and display a maintenance page."}
        </p>
      </div>

      {/* LangSmith Monitoring Section */}
      <div className="bg-card border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">LangSmith Monitoring</h2>

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
    </div>
  );
}
