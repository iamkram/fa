"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Calendar, FileText, ArrowRight, GitCompare } from "lucide-react";

interface SummaryHistoryItem {
  summary_id: string;
  generation_date: string;
  hook_text: string | null;
  medium_text: string | null;
  expanded_text: string | null;
  word_count: number;
}

interface SummaryDiff {
  added_sentences: string[];
  removed_sentences: string[];
  summary1: SummaryHistoryItem;
  summary2: SummaryHistoryItem;
}

interface SummaryHistoryProps {
  ticker: string;
}

export function SummaryHistory({ ticker }: SummaryHistoryProps) {
  const [summaries, setSummaries] = useState<SummaryHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSummaries, setSelectedSummaries] = useState<string[]>([]);
  const [diff, setDiff] = useState<SummaryDiff | null>(null);
  const [isComparing, setIsComparing] = useState(false);

  useEffect(() => {
    const fetchHistory = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `http://localhost:8000/api/stocks/${ticker}/summaries/history?limit=10`
        );

        if (!response.ok) {
          throw new Error("Failed to load summary history");
        }

        const data = await response.json();
        setSummaries(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load summary history"
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
  }, [ticker]);

  const handleSelectSummary = (summaryId: string) => {
    setSelectedSummaries((prev) => {
      if (prev.includes(summaryId)) {
        return prev.filter((id) => id !== summaryId);
      }
      if (prev.length >= 2) {
        return [prev[1], summaryId];
      }
      return [...prev, summaryId];
    });
    setDiff(null);
  };

  const handleCompare = async () => {
    if (selectedSummaries.length !== 2) return;

    setIsComparing(true);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8000/api/stocks/${ticker}/summaries/compare?summary1_id=${selectedSummaries[0]}&summary2_id=${selectedSummaries[1]}`
      );

      if (!response.ok) {
        throw new Error("Failed to compare summaries");
      }

      const data = await response.json();
      setDiff(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to compare summaries"
      );
    } finally {
      setIsComparing(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Summary History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error && !diff) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Summary History</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-center text-muted-foreground py-8">{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Summary History</CardTitle>
            {selectedSummaries.length === 2 && (
              <Button
                onClick={handleCompare}
                disabled={isComparing}
                size="sm"
                className="gap-2"
              >
                <GitCompare className="h-4 w-4" />
                Compare Selected
              </Button>
            )}
          </div>
          {selectedSummaries.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {selectedSummaries.length === 1
                ? "Select one more summary to compare"
                : "Two summaries selected - click Compare"}
            </p>
          )}
        </CardHeader>
        <CardContent>
          {summaries.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No summary history available
            </p>
          ) : (
            <div className="space-y-4">
              {summaries.map((summary, index) => (
                <div
                  key={summary.summary_id}
                  className={`border rounded-lg p-4 cursor-pointer transition-all ${
                    selectedSummaries.includes(summary.summary_id)
                      ? "border-primary bg-primary/5"
                      : "hover:border-primary/50"
                  }`}
                  onClick={() => handleSelectSummary(summary.summary_id)}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">
                        {formatDate(summary.generation_date)}
                      </span>
                      {index === 0 && (
                        <Badge variant="secondary">Latest</Badge>
                      )}
                      {selectedSummaries.includes(summary.summary_id) && (
                        <Badge variant="default">
                          Selected {selectedSummaries.indexOf(summary.summary_id) + 1}
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <FileText className="h-4 w-4" />
                      {summary.word_count} words
                    </div>
                  </div>
                  {summary.hook_text && (
                    <p className="text-sm font-medium mb-2">
                      {summary.hook_text}
                    </p>
                  )}
                  {summary.medium_text && (
                    <p className="text-sm text-muted-foreground line-clamp-3">
                      {summary.medium_text}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {diff && (
        <Card>
          <CardHeader>
            <CardTitle>Summary Comparison</CardTitle>
            <p className="text-sm text-muted-foreground">
              Showing changes between{" "}
              {formatDate(diff.summary1.generation_date)} and{" "}
              {formatDate(diff.summary2.generation_date)}
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            {diff.removed_sentences.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Badge variant="destructive">Removed</Badge>
                  {diff.removed_sentences.length} sentence
                  {diff.removed_sentences.length !== 1 ? "s" : ""}
                </h3>
                <div className="space-y-2">
                  {diff.removed_sentences.map((sentence, index) => (
                    <div
                      key={index}
                      className="text-sm p-3 bg-destructive/10 border border-destructive/20 rounded"
                    >
                      {sentence}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {diff.added_sentences.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Badge className="bg-green-500 hover:bg-green-600">
                    Added
                  </Badge>
                  {diff.added_sentences.length} sentence
                  {diff.added_sentences.length !== 1 ? "s" : ""}
                </h3>
                <div className="space-y-2">
                  {diff.added_sentences.map((sentence, index) => (
                    <div
                      key={index}
                      className="text-sm p-3 bg-green-50 border border-green-200 rounded"
                    >
                      {sentence}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {diff.removed_sentences.length === 0 &&
              diff.added_sentences.length === 0 && (
                <p className="text-center text-muted-foreground py-8">
                  No differences found between these summaries
                </p>
              )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
