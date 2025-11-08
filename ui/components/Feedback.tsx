"use client";

import { useState } from "react";
import { Button } from "./ui/button";
import { toast } from "sonner";

interface FeedbackProps {
  runId?: string;
  messageId: string;
}

export function Feedback({ runId, messageId }: FeedbackProps) {
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFeedback = async (score: number, type: "up" | "down") => {
    if (!runId) {
      toast.error("Unable to submit feedback", {
        description: "Run ID not available",
      });
      return;
    }

    setIsSubmitting(true);
    setFeedback(type);

    try {
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          runId,
          score,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to submit feedback");
      }

      toast.success("Thank you for your feedback!");
    } catch (error) {
      console.error("Failed to submit feedback:", error);
      toast.error("Failed to submit feedback", {
        description: "Please try again later",
      });
      setFeedback(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex gap-2 mt-3">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => handleFeedback(1, "up")}
        disabled={isSubmitting || feedback !== null}
        className={`text-xs ${
          feedback === "up"
            ? "bg-secondary text-primary"
            : "hover:bg-secondary"
        }`}
      >
        Thumbs up
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => handleFeedback(0, "down")}
        disabled={isSubmitting || feedback !== null}
        className={`text-xs ${
          feedback === "down"
            ? "bg-secondary text-destructive"
            : "hover:bg-secondary"
        }`}
      >
        Thumbs down
      </Button>
    </div>
  );
}
