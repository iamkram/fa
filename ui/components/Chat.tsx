"use client";

import { type Message } from "ai";
import { useChat } from "ai/react";
import { useState, useEffect, useRef } from "react";
import type { FormEvent } from "react";
import { toast } from "sonner";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { MessageBubble } from "./Message";
import { Button } from "./ui/button";
import { cn } from "@/utils/cn";
import { v4 as uuidv4 } from "uuid";
import { SuggestedPrompts } from "./SuggestedPrompts";
import { SessionSidebar, SidebarToggle } from "./SessionSidebar";
import {
  addMessageToSession,
  createNewSession,
  getSession,
  getCurrentSessionId,
  setCurrentSessionId,
} from "@/lib/sessionStorage";

function ScrollToBottom() {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  if (isAtBottom) return null;

  return (
    <Button
      variant="outline"
      className="absolute bottom-full left-1/2 -translate-x-1/2 mb-4"
      onClick={() => scrollToBottom()}
      size="sm"
    >
      Scroll to bottom
    </Button>
  );
}

function ChatMessages(props: {
  messages: Message[];
  sourcesForMessages: Record<string, any>;
  runIds: Record<string, string>;
  onPromptClick?: (text: string) => void;
  advisorName?: string;
  advisorFirm?: string;
}) {
  if (props.messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-4 py-8">
        <div className="max-w-4xl w-full">
          <h2 className="text-2xl font-semibold text-foreground mb-3">
            {props.advisorName
              ? `Welcome, ${props.advisorName}`
              : "Welcome to FA AI Assistant"}
          </h2>
          {props.advisorFirm && (
            <p className="text-sm text-muted-foreground mb-2">
              {props.advisorFirm}
            </p>
          )}
          <p className="text-muted-foreground mb-8">
            Ask questions about market trends, company analysis, or financial
            data. Your AI assistant is ready to help with professional insights.
          </p>

          {props.onPromptClick && (
            <SuggestedPrompts onPromptClick={props.onPromptClick} />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col max-w-[900px] mx-auto pb-12 w-full px-4">
      {props.messages.map((m, i) => {
        const sourceKey = (props.messages.length - 1 - i).toString();
        return (
          <MessageBubble
            key={m.id}
            message={m}
            sources={props.sourcesForMessages[sourceKey]}
            runId={props.runIds[m.id]}
          />
        );
      })}
    </div>
  );
}

function ChatInput(props: {
  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  loading?: boolean;
  placeholder?: string;
}) {
  return (
    <form
      onSubmit={props.onSubmit}
      className="flex w-full flex-col max-w-[900px] mx-auto px-4"
    >
      <div className="border border-input bg-background rounded-xl flex items-center gap-2 shadow-sm">
        <input
          value={props.value}
          placeholder={props.placeholder}
          onChange={props.onChange}
          disabled={props.loading}
          className="flex-1 border-none outline-none bg-transparent px-4 py-3 text-sm"
          autoFocus
        />
        <Button
          type="submit"
          disabled={props.loading || !props.value.trim()}
          className="mr-2"
          size="sm"
        >
          {props.loading ? "Sending..." : "Send"}
        </Button>
      </div>
    </form>
  );
}

function StickyToBottomContent(props: {
  content: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const context = useStickToBottomContext();

  return (
    <div
      ref={context.scrollRef}
      style={{ width: "100%", height: "100%" }}
      className="grid grid-rows-[1fr,auto]"
    >
      <div ref={context.contentRef} className="py-8">
        {props.content}
      </div>
      {props.footer}
    </div>
  );
}

function ChatLayout(props: { content: React.ReactNode; footer: React.ReactNode }) {
  return (
    <StickToBottom>
      <StickyToBottomContent
        content={props.content}
        footer={
          <div className="sticky bottom-8">
            <ScrollToBottom />
            {props.footer}
          </div>
        }
      />
    </StickToBottom>
  );
}

export function Chat() {
  const [sessionId, setSessionId] = useState(() => uuidv4());
  const [sourcesForMessages, setSourcesForMessages] = useState<
    Record<string, any>
  >({});
  const [runIds, setRunIds] = useState<Record<string, string>>({});
  const pendingRunIdRef = useRef<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [advisorName, setAdvisorName] = useState<string>("");
  const [advisorFirm, setAdvisorFirm] = useState<string>("");

  const chat = useChat({
    api: "/api/chat",
    body: {
      sessionId,
    },
    onResponse(response) {
      // Extract sources from header
      const sourcesHeader = response.headers.get("x-sources");
      const sources = sourcesHeader
        ? JSON.parse(Buffer.from(sourcesHeader, "base64").toString("utf8"))
        : [];

      const messageIndexHeader = response.headers.get("x-message-index");
      if (sources.length && messageIndexHeader !== null) {
        setSourcesForMessages({
          ...sourcesForMessages,
          [messageIndexHeader]: sources,
        });
      }

      // Extract run ID and store it temporarily in ref (not state to avoid closure issues)
      const runId = response.headers.get("x-run-id");
      console.log("📥 Received run ID from backend:", runId);
      if (runId) {
        pendingRunIdRef.current = runId;
      }
    },
    onFinish(message) {
      // Associate the pending run ID with the completed assistant message
      const currentRunId = pendingRunIdRef.current;
      console.log("✅ Message finished:", message.id, "Role:", message.role, "Pending run ID:", currentRunId);
      if (currentRunId && message.role === "assistant") {
        console.log("💾 Storing run ID:", currentRunId, "for message:", message.id);
        setRunIds((prev) => ({
          ...prev,
          [message.id]: currentRunId,
        }));
        pendingRunIdRef.current = null;
      }
    },
    streamMode: "text",
    onError: (e) => {
      toast.error("Error processing your request", {
        description: e.message,
      });
      pendingRunIdRef.current = null;
    },
  });

  // Handler for when a suggested prompt is clicked
  const handlePromptClick = (promptText: string) => {
    // Set the input value
    chat.setInput(promptText);

    // Submit the message by appending it to the messages
    chat.append({
      role: "user",
      content: promptText,
    });
  };

  // Session management handlers
  const handleNewChat = () => {
    const newSessionId = uuidv4();
    createNewSession(newSessionId);
    setSessionId(newSessionId);
    chat.setMessages([]);
    setSourcesForMessages({});
    setRunIds({});
  };

  const handleSessionChange = (newSessionId: string) => {
    const session = getSession(newSessionId);
    if (session) {
      setSessionId(newSessionId);
      setCurrentSessionId(newSessionId);

      // Convert stored messages to Message format
      const messages: Message[] = session.messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
      }));

      chat.setMessages(messages);
      setSidebarOpen(false); // Close sidebar on mobile
    }
  };

  // Save messages to localStorage whenever chat.messages changes
  useEffect(() => {
    if (chat.messages.length > 0) {
      chat.messages.forEach((msg) => {
        addMessageToSession(sessionId, {
          id: msg.id,
          role: msg.role,
          content: msg.content,
          timestamp: Date.now(),
        });
      });
    }
  }, [chat.messages, sessionId]);

  // Fetch advisor information on mount
  useEffect(() => {
    const fetchAdvisorInfo = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/advisors/FA-001");
        if (response.ok) {
          const data = await response.json();
          setAdvisorName(data.name);
          setAdvisorFirm(data.firm_name || "");
        }
      } catch (error) {
        console.error("Failed to fetch advisor info:", error);
      }
    };
    fetchAdvisorInfo();
  }, []);

  return (
    <div className="flex h-full w-full">
      <SessionSidebar
        currentSessionId={sessionId}
        onSessionChange={handleSessionChange}
        onNewChat={handleNewChat}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      <div className="flex-1 flex flex-col relative">
        <SidebarToggle onClick={() => setSidebarOpen(!sidebarOpen)} />

        <ChatLayout
          content={
            <ChatMessages
              messages={chat.messages}
              sourcesForMessages={sourcesForMessages}
              runIds={runIds}
              onPromptClick={handlePromptClick}
              advisorName={advisorName}
              advisorFirm={advisorFirm}
            />
          }
          footer={
            <ChatInput
              value={chat.input}
              onChange={chat.handleInputChange}
              onSubmit={chat.handleSubmit}
              loading={chat.isLoading}
              placeholder="Ask a question about markets, companies, or financial data..."
            />
          }
        />
      </div>
    </div>
  );
}
