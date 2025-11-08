import { NextRequest, NextResponse } from "next/server";
import { v4 as uuidv4 } from "uuid";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface Message {
  role: string;
  content: string;
  id?: string;
}

interface BackendResponse {
  query_id: string;
  response_text: string;
  response_tier?: string;
  processing_time_ms: number;
  guardrail_status: string;
  citations: any[];
  pii_flags: any[];
  run_id?: string;  // LangSmith run ID for feedback
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const messages: Message[] = body.messages ?? [];
    const sessionId = body.sessionId ?? uuidv4();

    // Get the current message (last in array)
    const currentMessage = messages[messages.length - 1];

    if (!currentMessage || currentMessage.role !== "user") {
      return NextResponse.json(
        { error: "Invalid message format" },
        { status: 400 }
      );
    }

    // Backend API URL
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    // Prepare request to backend
    const backendRequest = {
      fa_id: process.env.NEXT_PUBLIC_DEFAULT_FA_ID || "FA-001",
      session_id: sessionId,
      query_text: currentMessage.content,
      query_type: "chat",
      context: {}
    };

    // Call the backend API
    const response = await fetch(`${backendUrl}/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(backendRequest),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Backend API error: ${response.status}`);
    }

    const backendData: BackendResponse = await response.json();

    console.log("🔍 Backend response:", {
      query_id: backendData.query_id,
      run_id: backendData.run_id,
      has_run_id: !!backendData.run_id
    });

    // Prepare sources for header (following template pattern)
    const sources = backendData.citations || [];
    const sourcesHeader = sources.length > 0
      ? Buffer.from(JSON.stringify(sources)).toString("base64")
      : null;

    // Return streaming response with sources in header
    const headers: Record<string, string> = {
      "Content-Type": "text/plain; charset=utf-8",
    };

    if (sourcesHeader) {
      headers["x-sources"] = sourcesHeader;
      headers["x-message-index"] = (messages.length - 1).toString();
    }

    // Add run ID for feedback (use LangSmith run_id, not query_id)
    if (backendData.run_id) {
      console.log("✅ Setting x-run-id header:", backendData.run_id);
      headers["x-run-id"] = backendData.run_id;
    } else {
      console.warn("⚠️ No run_id in backend response!");
    }

    // Return the response as a stream
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        // Stream the response text
        controller.enqueue(encoder.encode(backendData.response_text));
        controller.close();
      },
    });

    return new Response(stream, { headers });

  } catch (error: any) {
    console.error("Chat API error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to process query" },
      { status: 500 }
    );
  }
}
