import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.AFTERMATH_API_BASE || "https://aftermath-api.onrender.com";

function allowed(method: string, path: string): boolean {
  if (path.startsWith("/internal") || (path.startsWith("/v1/events") && method !== "GET")) return false;
  if (method === "POST" && path === "/v1/decisions") return false;
  if (method === "GET" && ["/health", "/ready", "/v1/events", "/v1/decisions", "/v1/paper/fills", "/v1/ops/status", "/v1/metrics"].includes(path)) {
    return true;
  }
  if (method === "GET" && /^\/v1\/(events|evidence|decisions|instruments|receipts)\/[^/]+$/.test(path)) return true;
  if (method === "POST" && /^\/v1\/receipts\/[^/]+\/(verify|replay)$/.test(path)) return true;
  return false;
}

async function proxy(request: NextRequest, path: string) {
  if (!allowed(request.method, path)) {
    return NextResponse.json(
      { error: { code: "FORBIDDEN", message: "route is not on the reader allowlist", retryable: false } },
      { status: 403 },
    );
  }
  const token = process.env.AFTERMATH_API_TOKEN || "";
  if (!token) {
    return NextResponse.json(
      { error: { code: "SOURCE_UNAVAILABLE", message: "reader token is not configured", retryable: false } },
      { status: 503 },
    );
  }
  const target = new URL(BASE + path);
  const incoming = new URL(request.url);
  for (const key of ["limit", "cursor"]) {
    const value = incoming.searchParams.get(key);
    if (value) target.searchParams.set(key, value.slice(0, 200));
  }
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: { code: "SOURCE_UNAVAILABLE", message: "backend unavailable", retryable: true } },
      { status: 503 },
    );
  }
  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, `/${path.join("/")}`);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, `/${path.join("/")}`);
}
