"use client";

import { useState, useEffect } from "react";
import { Button } from "./ui/button";
import { cn } from "@/utils/cn";
import {
  getAllSessions,
  deleteSession,
  createNewSession,
  type ChatSession,
} from "@/lib/sessionStorage";

interface SessionSidebarProps {
  currentSessionId: string | null;
  onSessionChange: (sessionId: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

export function SessionSidebar({
  currentSessionId,
  onSessionChange,
  onNewChat,
  isOpen,
  onToggle,
}: SessionSidebarProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  // Load sessions from localStorage
  useEffect(() => {
    const loadSessions = () => {
      const allSessions = getAllSessions();
      setSessions(allSessions);
    };

    loadSessions();

    // Listen for storage events (sessions updated in another tab)
    window.addEventListener("storage", loadSessions);
    return () => window.removeEventListener("storage", loadSessions);
  }, [currentSessionId]); // Reload when current session changes

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent session selection
    if (confirm("Delete this chat?")) {
      deleteSession(sessionId);
      setSessions(getAllSessions());

      // If deleting current session, create new one
      if (sessionId === currentSessionId) {
        onNewChat();
      }
    }
  };

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return "Today";
    } else if (diffDays === 1) {
      return "Yesterday";
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed md:relative top-0 left-0 h-full bg-background border-r border-border flex flex-col transition-transform duration-300 z-50",
          "w-[280px]",
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold text-lg">Chat History</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            className="md:hidden"
          >
            ✕
          </Button>
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <Button
            onClick={onNewChat}
            className="w-full"
            variant="outline"
          >
            + New Chat
          </Button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              No chat history yet
            </div>
          ) : (
            <div className="space-y-1 p-2">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => onSessionChange(session.id)}
                  className={cn(
                    "w-full text-left p-3 rounded-lg transition-colors group relative",
                    "hover:bg-accent",
                    currentSessionId === session.id
                      ? "bg-accent"
                      : "bg-transparent"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">
                        {session.title}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {formatDate(session.updatedAt)}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDeleteSession(session.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-destructive/10 rounded transition-opacity"
                      title="Delete chat"
                    >
                      <svg
                        className="w-4 h-4 text-destructive"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer with session count */}
        <div className="p-4 border-t border-border text-xs text-muted-foreground text-center">
          {sessions.length} {sessions.length === 1 ? "chat" : "chats"}
        </div>
      </aside>
    </>
  );
}

/**
 * Toggle button for mobile sidebar
 */
export function SidebarToggle({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      className="md:hidden fixed top-4 left-4 z-30"
      title="Toggle sidebar"
    >
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4 6h16M4 12h16M4 18h16"
        />
      </svg>
    </Button>
  );
}
