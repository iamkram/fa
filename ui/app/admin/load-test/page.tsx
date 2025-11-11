"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { AdminNav } from "@/components/AdminNav";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

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
  const [initialLoading, setInitialLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<LoadTestRun | null>(null);
  const [failures, setFailures] = useState<FailureInfo[]>([]);
  const [errorSummary, setErrorSummary] = useState<ErrorSummary[]>([]);
  const [showFailures, setShowFailures] = useState(false);
  const [formData, setFormData] = useState({
    testName: "",
    concurrentUsers: 5,
    totalRequests: 50,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedRuns, setSelectedRuns] = useState<number[]>([]);
  const [showComparison, setShowComparison] = useState(false);

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
    } finally {
      setInitialLoading(false);
    }
  };

  const startLoadTest = async () => {
    if (!formData.testName.trim()) {
      toast.error("Test name required", {
        description: "Please provide a descriptive name for this load test to help identify it later.",
      });
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
      toast.success(`Load test started successfully`, {
        description: `Run ID ${data.run_id} - ${formData.totalRequests} requests from ${formData.concurrentUsers} concurrent users. Check results below.`,
        action: {
          label: "View LangSmith",
          onClick: () => window.open("https://smith.langchain.com", "_blank"),
        },
      });

      // Clear form
      setFormData({ testName: "", concurrentUsers: 5, totalRequests: 50 });

      // Refresh runs
      await fetchRuns();
    } catch (error: any) {
      toast.error("Failed to start load test", {
        description: error.message || "Unable to connect to the backend. Ensure the server is running and accessible.",
        action: {
          label: "Retry",
          onClick: () => startLoadTest(),
        },
      });
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

      toast.success(`Load test stopped`, {
        description: `Run ID ${runId} has been terminated. Partial results are available below.`,
      });
      await fetchRuns();
    } catch (error: any) {
      toast.error("Failed to stop load test", {
        description: error.message || "Unable to stop the test. It may have already completed.",
        action: {
          label: "Refresh",
          onClick: () => fetchRuns(),
        },
      });
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

  const exportToCSV = () => {
    const headers = [
      "Run ID",
      "Test Name",
      "Status",
      "Concurrent Users",
      "Total Requests",
      "Completed",
      "Failed",
      "Success Rate %",
      "Avg Response (ms)",
      "P95 Response (ms)",
      "P99 Response (ms)",
      "Throughput (req/s)",
      "Started At",
      "Completed At",
    ];

    const rows = runs.map((run) => [
      run.id,
      run.test_name,
      run.status,
      run.concurrent_users,
      run.total_requests,
      run.requests_completed,
      run.requests_failed,
      run.requests_completed
        ? Math.round(
            (run.requests_completed /
              (run.requests_completed + run.requests_failed)) *
              100
          )
        : 0,
      run.avg_response_time_ms?.toFixed(0) || "",
      run.p95_response_time_ms?.toFixed(0) || "",
      run.p99_response_time_ms?.toFixed(0) || "",
      run.requests_per_second?.toFixed(2) || "",
      run.started_at || "",
      run.completed_at || "",
    ]);

    const csv = [headers, ...rows].map((row) => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `load-test-results-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    toast.success("CSV exported successfully", {
      description: `Downloaded ${runs.length} test results`,
    });
  };

  const exportToJSON = () => {
    const json = JSON.stringify(runs, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `load-test-results-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);

    toast.success("JSON exported successfully", {
      description: `Downloaded ${runs.length} test results`,
    });
  };

  // Filter runs based on search query and status
  const filteredRuns = runs.filter((run) => {
    const matchesSearch =
      searchQuery === "" ||
      run.test_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      run.id.toString().includes(searchQuery);

    const matchesStatus =
      statusFilter === "all" || run.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  const toggleRunSelection = (runId: number) => {
    setSelectedRuns((prev) =>
      prev.includes(runId)
        ? prev.filter((id) => id !== runId)
        : [...prev, runId]
    );
  };

  const selectedRunsData = runs.filter((run) => selectedRuns.includes(run.id));

  return (
    <div className="container mx-auto p-8 max-w-7xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-4">Load Testing Dashboard</h1>

        {/* Navigation */}
        <AdminNav />
      </div>

      {/* Performance Trends */}
      {runs.filter(r => r.status === "completed" && r.avg_response_time_ms).length > 0 && (
        <div className="bg-card border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-6">Performance Trends</h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Response Time Trend */}
            <div>
              <h3 className="text-sm font-medium mb-4 text-muted-foreground">Average Response Time</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart
                  data={runs
                    .filter(r => r.status === "completed" && r.avg_response_time_ms)
                    .reverse()
                    .slice(-10)
                    .map(r => ({
                      name: `Run ${r.id}`,
                      avgTime: r.avg_response_time_ms,
                      p95Time: r.p95_response_time_ms,
                      p99Time: r.p99_response_time_ms,
                    }))}
                  margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="name" className="text-xs" />
                  <YAxis className="text-xs" label={{ value: 'ms', angle: -90, position: 'insideLeft' }} />
                  <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }} />
                  <Legend />
                  <Line type="monotone" dataKey="avgTime" stroke="hsl(var(--primary))" name="Avg" strokeWidth={2} />
                  <Line type="monotone" dataKey="p95Time" stroke="hsl(var(--destructive))" name="P95" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Success Rate Trend */}
            <div>
              <h3 className="text-sm font-medium mb-4 text-muted-foreground">Success Rate</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={runs
                    .filter(r => r.status === "completed")
                    .reverse()
                    .slice(-10)
                    .map(r => ({
                      name: `Run ${r.id}`,
                      successRate: Math.round(
                        (r.requests_completed / (r.requests_completed + r.requests_failed)) * 100
                      ),
                    }))}
                  margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="name" className="text-xs" />
                  <YAxis className="text-xs" domain={[0, 100]} label={{ value: '%', angle: -90, position: 'insideLeft' }} />
                  <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }} />
                  <Bar dataKey="successRate" fill="hsl(var(--primary))" name="Success Rate %" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Start New Load Test */}
      <div id="start-test-form" className="bg-card border rounded-lg p-6 mb-8">
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
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Starting...
            </>
          ) : (
            "Start Load Test"
          )}
        </Button>

        <p className="text-sm text-muted-foreground mt-4">
          This will simulate {formData.concurrentUsers} financial advisors making{" "}
          {formData.totalRequests} total queries to test system performance.
        </p>
      </div>

      {/* Test Runs List */}
      <div className="bg-card border rounded-lg p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold">Recent Test Runs</h2>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span>Auto-refresh: 5s</span>
            </div>
          </div>
          {runs.length > 0 && (
            <div className="flex gap-2">
              {selectedRuns.length >= 2 && (
                <Button
                  onClick={() => setShowComparison(true)}
                  variant="default"
                  size="sm"
                  className="text-xs"
                >
                  Compare Selected ({selectedRuns.length})
                </Button>
              )}
              <Button
                onClick={exportToCSV}
                variant="outline"
                size="sm"
                className="text-xs"
              >
                Export CSV
              </Button>
              <Button
                onClick={exportToJSON}
                variant="outline"
                size="sm"
                className="text-xs"
              >
                Export JSON
              </Button>
            </div>
          )}
        </div>

        {/* Filter Controls */}
        {runs.length > 0 && (
          <div className="flex flex-col sm:flex-row gap-3 mb-4 pb-4 border-b">
            <div className="flex-1">
              <Input
                placeholder="Search by test name or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="max-w-sm"
              />
            </div>
            <div className="flex gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="all">All Status</option>
                <option value="running">Running</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
              </select>
              {(searchQuery || statusFilter !== "all") && (
                <Button
                  onClick={() => {
                    setSearchQuery("");
                    setStatusFilter("all");
                  }}
                  variant="outline"
                  size="sm"
                >
                  Clear Filters
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Result count */}
        {runs.length > 0 && filteredRuns.length !== runs.length && (
          <div className="mb-4 text-sm text-muted-foreground">
            Showing {filteredRuns.length} of {runs.length} test runs
          </div>
        )}

        {initialLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="border rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Skeleton className="h-5 w-48" />
                      <Skeleton className="h-6 w-20" />
                    </div>
                    <Skeleton className="h-4 w-32" />
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-3">
                  <div>
                    <Skeleton className="h-3 w-20 mb-1" />
                    <Skeleton className="h-5 w-12" />
                  </div>
                  <div>
                    <Skeleton className="h-3 w-24 mb-1" />
                    <Skeleton className="h-5 w-16" />
                  </div>
                  <div>
                    <Skeleton className="h-3 w-20 mb-1" />
                    <Skeleton className="h-5 w-12" />
                  </div>
                  <div>
                    <Skeleton className="h-3 w-16 mb-1" />
                    <Skeleton className="h-5 w-8" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <div className="w-16 h-16 mb-4 rounded-full bg-secondary flex items-center justify-center">
              <svg
                className="w-8 h-8 text-muted-foreground"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold mb-2">No Load Tests Yet</h3>
            <p className="text-muted-foreground text-center max-w-md mb-4">
              Start your first load test to benchmark system performance and identify bottlenecks.
            </p>
            <Button
              onClick={() => {
                const element = document.getElementById('start-test-form');
                element?.scrollIntoView({ behavior: 'smooth' });
              }}
              variant="outline"
              size="sm"
            >
              Configure Load Test →
            </Button>
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <div className="w-16 h-16 mb-4 rounded-full bg-secondary flex items-center justify-center">
              <svg
                className="w-8 h-8 text-muted-foreground"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold mb-2">No Results Found</h3>
            <p className="text-muted-foreground text-center max-w-md mb-4">
              No test runs match your current filters. Try adjusting your search criteria.
            </p>
            <Button
              onClick={() => {
                setSearchQuery("");
                setStatusFilter("all");
              }}
              variant="outline"
              size="sm"
            >
              Clear Filters
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredRuns.map((run) => (
              <div
                key={run.id}
                className="border rounded-lg p-4 hover:bg-secondary/50 transition-colors cursor-pointer"
                onClick={() => viewRunDetails(run)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3 flex-1">
                    <input
                      type="checkbox"
                      checked={selectedRuns.includes(run.id)}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleRunSelection(run.id);
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
                    />
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

                {/* Progress Bar for Running Tests */}
                {run.status === "running" && (
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                        Test in progress...
                      </span>
                      <span className="text-xs font-medium">
                        {Math.round(((run.requests_completed || 0) / run.total_requests) * 100)}%
                      </span>
                    </div>
                    <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 transition-all duration-500 ease-out"
                        style={{
                          width: `${Math.min(
                            ((run.requests_completed || 0) / run.total_requests) * 100,
                            100
                          )}%`,
                        }}
                      />
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-xs text-muted-foreground">
                        {run.requests_completed || 0} / {run.total_requests} requests
                      </span>
                      {run.requests_per_second && (
                        <span className="text-xs text-muted-foreground">
                          {run.requests_per_second.toFixed(1)} req/s
                        </span>
                      )}
                    </div>
                  </div>
                )}

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
                    <p className={`font-semibold ${
                      run.requests_completed
                        ? Math.round(
                            (run.requests_completed /
                              (run.requests_completed + run.requests_failed)) *
                              100
                          ) >= 95
                          ? "text-green-600"
                          : Math.round(
                              (run.requests_completed /
                                (run.requests_completed + run.requests_failed)) *
                                100
                            ) >= 80
                          ? "text-yellow-600"
                          : "text-red-600"
                        : ""
                    }`}>
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

      {/* Selected Run Details Modal */}
      <Dialog open={!!selectedRun} onOpenChange={(open) => !open && setSelectedRun(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-2xl">{selectedRun?.test_name}</DialogTitle>
            <DialogDescription>
              Detailed performance metrics and failure analysis for Run ID {selectedRun?.id}
            </DialogDescription>
          </DialogHeader>

          {selectedRun && (
            <div className="space-y-6 py-4">
              {/* Test Overview Section */}
              <div className="bg-secondary/30 rounded-lg p-4">
                <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Test Overview</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Status</p>
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(
                        selectedRun.status
                      )}`}
                    >
                      {selectedRun.status.toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Run ID</p>
                    <p className="text-base font-semibold">{selectedRun.id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Started At</p>
                    <p className="text-sm font-medium">
                      {selectedRun.started_at
                        ? new Date(selectedRun.started_at).toLocaleString()
                        : "Not started"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Completed At</p>
                    <p className="text-sm font-medium">
                      {selectedRun.completed_at
                        ? new Date(selectedRun.completed_at).toLocaleString()
                        : "Not completed"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Performance Metrics Section */}
              {selectedRun.status === "completed" &&
                selectedRun.avg_response_time_ms && (
                  <div className="bg-secondary/30 rounded-lg p-4">
                    <h3 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">Performance Metrics</h3>
                    <div className="grid grid-cols-2 gap-6">
                      <div className="bg-card p-3 rounded-lg border">
                        <p className="text-xs text-muted-foreground mb-1">
                          Average Response Time
                        </p>
                        <p className="text-3xl font-bold text-primary">
                          {selectedRun.avg_response_time_ms.toFixed(0)}
                          <span className="text-sm font-normal text-muted-foreground ml-1">ms</span>
                        </p>
                      </div>
                      <div className="bg-card p-3 rounded-lg border">
                        <p className="text-xs text-muted-foreground mb-1">
                          Throughput
                        </p>
                        <p className="text-3xl font-bold text-primary">
                          {selectedRun.requests_per_second?.toFixed(2)}
                          <span className="text-sm font-normal text-muted-foreground ml-1">req/s</span>
                        </p>
                      </div>
                      <div className="bg-card p-3 rounded-lg border">
                        <p className="text-xs text-muted-foreground mb-1">
                          P95 Latency
                        </p>
                        <p className="text-3xl font-bold text-primary">
                          {selectedRun.p95_response_time_ms?.toFixed(0)}
                          <span className="text-sm font-normal text-muted-foreground ml-1">ms</span>
                        </p>
                      </div>
                      <div className="bg-card p-3 rounded-lg border">
                        <p className="text-xs text-muted-foreground mb-1">
                          Success Rate
                        </p>
                        <p className={`text-3xl font-bold ${
                          Math.round(
                            (selectedRun.requests_completed /
                              (selectedRun.requests_completed +
                                selectedRun.requests_failed)) *
                              100
                          ) >= 95 ? "text-green-600" : "text-yellow-600"
                        }`}>
                          {Math.round(
                            (selectedRun.requests_completed /
                              (selectedRun.requests_completed +
                                selectedRun.requests_failed)) *
                              100
                          )}
                          <span className="text-sm font-normal text-muted-foreground ml-1">%</span>
                        </p>
                      </div>
                    </div>
                  </div>
                )}

              {/* Failures Section */}
              {selectedRun.requests_failed > 0 && (
                <div className="bg-red-50 dark:bg-red-950/20 rounded-lg p-4 border border-red-200 dark:border-red-900">
                  <div className="flex justify-between items-center mb-4">
                    <div>
                      <h3 className="text-sm font-semibold text-red-700 dark:text-red-400 uppercase tracking-wide">
                        Failures
                      </h3>
                      <p className="text-xs text-red-600 dark:text-red-500 mt-1">
                        {selectedRun.requests_failed} request{selectedRun.requests_failed > 1 ? 's' : ''} failed
                      </p>
                    </div>
                    <Button
                      onClick={() => setShowFailures(!showFailures)}
                      variant="outline"
                      size="sm"
                      className="border-red-300 hover:bg-red-100 dark:border-red-800 dark:hover:bg-red-900/50"
                    >
                      {showFailures ? "Hide Details" : "View Details"}
                    </Button>
                  </div>

                  {showFailures && (
                    <div className="space-y-4 mt-4">
                      {/* Error Summary */}
                      {errorSummary.length > 0 && (
                        <div className="bg-white dark:bg-card border border-red-300 dark:border-red-800 rounded-lg p-4">
                          <h4 className="font-semibold text-sm mb-3 text-red-900 dark:text-red-300">
                            Error Summary
                          </h4>
                          <div className="space-y-3">
                            {errorSummary.map((error, idx) => (
                              <div
                                key={idx}
                                className="flex justify-between items-start gap-4 p-3 bg-red-50 dark:bg-red-950/30 rounded border border-red-200 dark:border-red-900"
                              >
                                <div className="flex-1">
                                  <p className="font-medium text-sm text-red-900 dark:text-red-300">
                                    {error.error_type}
                                  </p>
                                  <p className="text-xs text-red-700 dark:text-red-500 mt-1">
                                    {error.count} occurrence{error.count > 1 ? "s" : ""}
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
                                    className="shrink-0"
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
                      <div>
                        <h4 className="font-semibold text-sm mb-3 text-red-900 dark:text-red-300">
                          Individual Failures
                        </h4>
                        <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                          {failures.slice(0, 10).map((failure, idx) => (
                            <div
                              key={idx}
                              className="bg-white dark:bg-card border border-red-200 dark:border-red-900 rounded-lg p-3"
                            >
                              <div className="flex justify-between items-start mb-2 gap-3">
                                <div className="flex-1">
                                  <span className="font-semibold text-sm text-red-900 dark:text-red-300">
                                    {failure.fa_id}
                                  </span>
                                  <span className="text-xs text-red-700 dark:text-red-500 ml-2">
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
                                    className="shrink-0"
                                  >
                                    View in LangSmith
                                  </Button>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground mb-2">
                                <span className="font-medium">Query:</span> {failure.query_text.substring(0, 80)}...
                              </p>
                              {failure.error_message && (
                                <p className="text-xs text-red-800 dark:text-red-400 font-mono bg-red-100 dark:bg-red-950/50 p-2 rounded border border-red-200 dark:border-red-900">
                                  {failure.error_message.substring(0, 200)}
                                </p>
                              )}
                            </div>
                          ))}
                          {failures.length > 10 && (
                            <p className="text-sm text-muted-foreground text-center py-2">
                              Showing first 10 of {failures.length} failures
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
