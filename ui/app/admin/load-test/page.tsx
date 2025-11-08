"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

interface LoadTestRun {
  id: number;
  test_name: string;
  status: string;
  concurrent_users: number;
  total_requests: number;
  requests_completed: number;
  requests_failed: number;
  avg_response_time_ms?: number;
  p50_response_time_ms?: number;
  p95_response_time_ms?: number;
  p99_response_time_ms?: number;
  requests_per_second?: number;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

interface FailureInfo {
  fa_id: string;
  query_text: string;
  error_message: string;
  langsmith_url?: string;
  response_time_ms: number;
  status_code: number;
  sent_at: string;
}

interface ErrorSummary {
  error_type: string;
  count: number;
  example_langsmith_url?: string;
}

export default function LoadTestPage() {
  const [runs, setRuns] = useState<LoadTestRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRun, setSelectedRun] = useState<LoadTestRun | null>(null);
  const [failures, setFailures] = useState<FailureInfo[]>([]);
  const [errorSummary, setErrorSummary] = useState<ErrorSummary[]>([]);
  const [showFailures, setShowFailures] = useState(false);
  const [formData, setFormData] = useState({
    testName: "",
    concurrentUsers: 5,
    totalRequests: 50,
  });

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(fetchRuns, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchRuns = async () => {
    try {
      const response = await fetch(`${backendUrl}/load-test/runs`);
      const data = await response.json();
      if (data.success) {
        setRuns(data.runs);
      }
    } catch (error) {
      console.error("Failed to fetch runs:", error);
    }
  };

  const startLoadTest = async () => {
    if (!formData.testName.trim()) {
      toast.error("Please provide a test name");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${backendUrl}/load-test/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          test_name: formData.testName,
          concurrent_users: formData.concurrentUsers,
          total_requests: formData.totalRequests,
          query_type: "chat",
          initiated_by: "admin-ui",
        }),
      });

      if (!response.ok) throw new Error("Failed to start load test");

      const data = await response.json();
      toast.success(`Load test started: Run ID ${data.run_id}`);

      // Clear form
      setFormData({ testName: "", concurrentUsers: 5, totalRequests: 50 });

      // Refresh runs
      await fetchRuns();
    } catch (error: any) {
      toast.error(error.message || "Failed to start load test");
    } finally {
      setLoading(false);
    }
  };

  const stopLoadTest = async (runId: number) => {
    try {
      const response = await fetch(`${backendUrl}/load-test/runs/${runId}/stop`, {
        method: "POST",
      });

      if (!response.ok) throw new Error("Failed to stop load test");

      toast.success(`Load test ${runId} stopped`);
      await fetchRuns();
    } catch (error: any) {
      toast.error(error.message || "Failed to stop load test");
    }
  };

  const fetchFailures = async (runId: number) => {
    try {
      const response = await fetch(`${backendUrl}/load-test/runs/${runId}/failures`);
      const data = await response.json();
      if (data.success) {
        setFailures(data.failures || []);
        setErrorSummary(data.error_summary || []);
      }
    } catch (error) {
      console.error("Failed to fetch failures:", error);
    }
  };

  const viewRunDetails = async (run: LoadTestRun) => {
    setSelectedRun(run);
    if (run.requests_failed > 0) {
      await fetchFailures(run.id);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "running":
        return "bg-blue-100 text-blue-800";
      case "failed":
        return "bg-red-100 text-red-800";
      case "cancelled":
        return "bg-gray-100 text-gray-800";
      default:
        return "bg-yellow-100 text-yellow-800";
    }
  };

  return (
    <div className="container mx-auto p-8 max-w-7xl">
      <h1 className="text-3xl font-bold mb-8">Load Testing Dashboard</h1>

      {/* Start New Load Test */}
      <div className="bg-card border rounded-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Start New Load Test</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium mb-2">
              Test Name <span className="text-red-500">*</span>
            </label>
            <Input
              value={formData.testName}
              onChange={(e) =>
                setFormData({ ...formData, testName: e.target.value })
              }
              placeholder="e.g., Performance Test 1"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Concurrent Users
            </label>
            <Input
              type="number"
              min="1"
              max="100"
              value={formData.concurrentUsers}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  concurrentUsers: parseInt(e.target.value),
                })
              }
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Total Requests
            </label>
            <Input
              type="number"
              min="1"
              max="1000"
              value={formData.totalRequests}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  totalRequests: parseInt(e.target.value),
                })
              }
              disabled={loading}
            />
          </div>
        </div>

        <Button
          onClick={startLoadTest}
          disabled={loading}
          className="w-full md:w-auto"
        >
          {loading ? "Starting..." : "Start Load Test"}
        </Button>

        <p className="text-sm text-muted-foreground mt-4">
          This will simulate {formData.concurrentUsers} financial advisors making{" "}
          {formData.totalRequests} total queries to test system performance.
        </p>
      </div>

      {/* Test Runs List */}
      <div className="bg-card border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Recent Test Runs</h2>

        {runs.length === 0 ? (
          <p className="text-muted-foreground text-center py-8">
            No load tests have been run yet. Start one above!
          </p>
        ) : (
          <div className="space-y-4">
            {runs.map((run) => (
              <div
                key={run.id}
                className="border rounded-lg p-4 hover:bg-secondary/50 transition-colors cursor-pointer"
                onClick={() => viewRunDetails(run)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-semibold">{run.test_name}</h3>
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                          run.status
                        )}`}
                      >
                        {run.status.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Run ID: {run.id} • Created:{" "}
                      {new Date(run.created_at).toLocaleString()}
                    </p>
                  </div>

                  {run.status === "running" && (
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        stopLoadTest(run.id);
                      }}
                      variant="destructive"
                      size="sm"
                    >
                      Stop
                    </Button>
                  )}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Concurrent Users</p>
                    <p className="font-semibold">{run.concurrent_users}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Total Requests</p>
                    <p className="font-semibold">{run.total_requests}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Completed</p>
                    <p className="font-semibold">
                      {run.requests_completed || 0} /{" "}
                      {run.requests_failed + (run.requests_completed || 0)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Success Rate</p>
                    <p className="font-semibold">
                      {run.requests_completed
                        ? Math.round(
                            (run.requests_completed /
                              (run.requests_completed + run.requests_failed)) *
                              100
                          )
                        : 0}
                      %
                    </p>
                  </div>
                </div>

                {run.status === "completed" && run.avg_response_time_ms && (
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm mt-4 pt-4 border-t">
                    <div>
                      <p className="text-muted-foreground">Avg Response</p>
                      <p className="font-semibold">
                        {run.avg_response_time_ms.toFixed(0)}ms
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">P50</p>
                      <p className="font-semibold">
                        {run.p50_response_time_ms?.toFixed(0)}ms
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">P95</p>
                      <p className="font-semibold">
                        {run.p95_response_time_ms?.toFixed(0)}ms
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">P99</p>
                      <p className="font-semibold">
                        {run.p99_response_time_ms?.toFixed(0)}ms
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Throughput</p>
                      <p className="font-semibold">
                        {run.requests_per_second?.toFixed(2)} req/s
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Selected Run Details Modal (future enhancement) */}
      {selectedRun && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-auto">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-2xl font-bold">{selectedRun.test_name}</h2>
              <Button
                onClick={() => setSelectedRun(null)}
                variant="ghost"
                size="sm"
              >
                ✕
              </Button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <span
                    className={`inline-block px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                      selectedRun.status
                    )}`}
                  >
                    {selectedRun.status.toUpperCase()}
                  </span>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Run ID</p>
                  <p className="font-semibold">{selectedRun.id}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Started At</p>
                  <p className="font-semibold">
                    {selectedRun.started_at
                      ? new Date(selectedRun.started_at).toLocaleString()
                      : "Not started"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Completed At</p>
                  <p className="font-semibold">
                    {selectedRun.completed_at
                      ? new Date(selectedRun.completed_at).toLocaleString()
                      : "Not completed"}
                  </p>
                </div>
              </div>

              {selectedRun.status === "completed" &&
                selectedRun.avg_response_time_ms && (
                  <div className="border-t pt-4">
                    <h3 className="font-semibold mb-3">Performance Metrics</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">
                          Average Response Time
                        </p>
                        <p className="text-2xl font-bold">
                          {selectedRun.avg_response_time_ms.toFixed(0)}ms
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">
                          Throughput
                        </p>
                        <p className="text-2xl font-bold">
                          {selectedRun.requests_per_second?.toFixed(2)} req/s
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">
                          P95 Latency
                        </p>
                        <p className="text-2xl font-bold">
                          {selectedRun.p95_response_time_ms?.toFixed(0)}ms
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">
                          Success Rate
                        </p>
                        <p className="text-2xl font-bold">
                          {Math.round(
                            (selectedRun.requests_completed /
                              (selectedRun.requests_completed +
                                selectedRun.requests_failed)) *
                              100
                          )}
                          %
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Failures Section */}
                {selectedRun.requests_failed > 0 && (
                  <div className="border-t pt-4 mt-4">
                    <div className="flex justify-between items-center mb-3">
                      <h3 className="font-semibold text-red-600">
                        Failures ({selectedRun.requests_failed})
                      </h3>
                      <Button
                        onClick={() => setShowFailures(!showFailures)}
                        variant="outline"
                        size="sm"
                      >
                        {showFailures ? "Hide Failures" : "View Failures"}
                      </Button>
                    </div>

                    {showFailures && (
                      <div className="space-y-4">
                        {/* Error Summary */}
                        {errorSummary.length > 0 && (
                          <div className="bg-red-50 border border-red-200 rounded p-3">
                            <h4 className="font-medium text-sm mb-2">
                              Error Summary
                            </h4>
                            <div className="space-y-2">
                              {errorSummary.map((error, idx) => (
                                <div
                                  key={idx}
                                  className="flex justify-between items-start text-sm"
                                >
                                  <div className="flex-1">
                                    <p className="font-medium">
                                      {error.error_type}
                                    </p>
                                    <p className="text-muted-foreground">
                                      {error.count} occurrence
                                      {error.count > 1 ? "s" : ""}
                                    </p>
                                  </div>
                                  {error.example_langsmith_url && (
                                    <Button
                                      onClick={() =>
                                        window.open(
                                          error.example_langsmith_url,
                                          "_blank"
                                        )
                                      }
                                      variant="outline"
                                      size="sm"
                                    >
                                      Debug in LangSmith →
                                    </Button>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Individual Failures */}
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                          {failures.slice(0, 10).map((failure, idx) => (
                            <div
                              key={idx}
                              className="bg-red-50 border border-red-200 rounded p-3 text-sm"
                            >
                              <div className="flex justify-between items-start mb-2">
                                <div>
                                  <span className="font-medium">
                                    {failure.fa_id}
                                  </span>
                                  <span className="text-muted-foreground ml-2">
                                    Status: {failure.status_code}
                                  </span>
                                </div>
                                {failure.langsmith_url && (
                                  <Button
                                    onClick={() =>
                                      window.open(failure.langsmith_url, "_blank")
                                    }
                                    variant="outline"
                                    size="sm"
                                  >
                                    🔍 LangSmith
                                  </Button>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground mb-1">
                                Query: {failure.query_text.substring(0, 80)}...
                              </p>
                              {failure.error_message && (
                                <p className="text-xs text-red-700 font-mono">
                                  {failure.error_message.substring(0, 200)}
                                </p>
                              )}
                            </div>
                          ))}
                          {failures.length > 10 && (
                            <p className="text-sm text-muted-foreground text-center">
                              Showing first 10 of {failures.length} failures
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
