import { NextRequest, NextResponse } from "next/server";
import { Client } from "langsmith";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface FeedbackRequest {
  runId: string;
  score: number; // 1 for thumbs up, 0 for thumbs down
  comment?: string;
}

export async function POST(req: NextRequest) {
  try {
    const body: FeedbackRequest = await req.json();
    const { runId, score, comment } = body;

    if (!runId) {
      return NextResponse.json(
        { error: "runId is required" },
        { status: 400 }
      );
    }

    // Initialize LangSmith client
    const client = new Client({
      apiKey: process.env.LANGSMITH_API_KEY,
    });

    // Create feedback in LangSmith
    await client.createFeedback(runId, "user_feedback", {
      score,
      comment: comment || undefined,
      feedbackSourceType: "app",
    });

    return NextResponse.json({
      success: true,
      message: "Feedback submitted successfully",
    });

  } catch (error: any) {
    console.error("Feedback API error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to submit feedback" },
      { status: 500 }
    );
  }
}
