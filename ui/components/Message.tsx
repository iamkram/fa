"use client";

import { cn } from "@/utils/cn";
import type { Message } from "ai/react";
import { Feedback } from "./Feedback";

interface MessageProps {
  message: Message;
  sources?: any[];
  runId?: string;
}

export function MessageBubble({ message, sources, runId }: MessageProps) {
  const isUser = message.role === "user";

  if (!isUser) {
    console.log("🔵 Rendering assistant message:", message.id, "with runId:", runId);
  }

  return (
    <div
      className={cn(
        "rounded-2xl max-w-[85%] mb-6 flex flex-col",
        isUser ? "ml-auto" : "mr-auto"
      )}
    >
      <div
        className={cn(
          "rounded-2xl px-5 py-3",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-secondary text-secondary-foreground"
        )}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>

      {!isUser && sources && sources.length > 0 && (
        <div className="mt-3 pl-2">
          <div className="text-xs font-semibold text-muted-foreground mb-2">
            Sources:
          </div>
          <div className="space-y-2">
            {sources.map((source: any, i: number) => (
              <div
                key={`source-${i}`}
                className="text-xs bg-muted/50 px-3 py-2 rounded-lg border border-border"
              >
                <div className="font-medium text-foreground mb-1">
                  {i + 1}. {source.metadata?.source || "Unknown source"}
                </div>
                {source.pageContent && (
                  <div className="text-muted-foreground line-clamp-2">
                    {source.pageContent}
                  </div>
                )}
                {source.metadata?.url && (
                  <a
                    href={source.metadata.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline mt-1 inline-block"
                  >
                    View source
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!isUser && <Feedback runId={runId} messageId={message.id} />}
    </div>
  );
}
