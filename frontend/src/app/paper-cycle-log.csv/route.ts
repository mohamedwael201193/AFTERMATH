import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BASE = process.env.AFTERMATH_API_BASE || "https://aftermath-api.onrender.com";

export async function GET() {
  try {
    const upstream = await fetch(BASE + "/paper-cycle-log.csv", { cache: "no-store" });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": "text/csv; charset=utf-8", "cache-control": "no-store" },
    });
  } catch {
    return new NextResponse("timestamp_utc\n", {
      status: 503,
      headers: { "content-type": "text/csv; charset=utf-8", "cache-control": "no-store" },
    });
  }
}

export async function POST() {
  return NextResponse.json(
    { error: { code: "FORBIDDEN", message: "the cycle log is read-only", retryable: false } },
    { status: 405 },
  );
}
