import type { Beach, BeachReport, ChatEvent } from "./types";

const SERVER_BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8765";

// Server-side fetches always go direct to the backend.
const API_BASE =
  typeof window === "undefined" ? `${SERVER_BACKEND_URL}/api` : "/api";

// Client-side streaming has to bypass Next.js's dev proxy (it buffers SSE).
// We hit the backend directly. Resolution order:
//   1. NEXT_PUBLIC_BACKEND_URL if explicitly set (e.g. for advanced setups).
//   2. Same hostname as the page, on backend port (default 8765). This is
//      what lets phones on your Wi-Fi work — they load the page from the
//      home server's LAN IP and the streaming URL inherits that hostname.
//   3. http://127.0.0.1:8765 fallback (server-side rendering, won't be hit
//      from the browser).
const BACKEND_PORT = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8765";

function resolveStreamBase(): string {
  if (process.env.NEXT_PUBLIC_BACKEND_URL) {
    return `${process.env.NEXT_PUBLIC_BACKEND_URL.replace(/\/$/, "")}/api`;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:${BACKEND_PORT}/api`;
  }
  return `${SERVER_BACKEND_URL}/api`;
}

export async function listBeaches(query?: string): Promise<Beach[]> {
  const url = query ? `${API_BASE}/beaches?q=${encodeURIComponent(query)}` : `${API_BASE}/beaches`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`listBeaches failed: ${res.status}`);
  const data = await res.json();
  return data.beaches as Beach[];
}

export async function getBeachReport(slug: string): Promise<BeachReport> {
  const res = await fetch(`${API_BASE}/beaches/${slug}/report`, { cache: "no-store" });
  if (!res.ok) throw new Error(`report failed: ${res.status}`);
  return (await res.json()) as BeachReport;
}

type StreamLogger = (line: string) => void;

export async function streamChat(
  messages: { role: string; content: string }[],
  onEvent: (e: ChatEvent) => void,
  options: { signal?: AbortSignal; log?: StreamLogger } = {},
): Promise<void> {
  const { signal, log = () => {} } = options;
  const url = `${resolveStreamBase()}/chat`;
  const body = JSON.stringify({ messages });
  log(`POST ${url}  body=${messages.length} msg(s) last=${messages.at(-1)?.role}/${(messages.at(-1)?.content ?? "").slice(0, 40)}`);

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body,
      signal,
      cache: "no-store",
    });
  } catch (err) {
    log(`fetch threw: ${(err as Error).message}`);
    throw err;
  }

  log(`response ${res.status} ${res.headers.get("content-type") ?? ""}`);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`chat HTTP ${res.status}: ${body.slice(0, 200)}`);
  }
  if (!res.body) {
    throw new Error("chat response has no body (no streaming reader)");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let bytesIn = 0;
  let eventsOut = 0;

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        log(`stream done (bytes=${bytesIn} events=${eventsOut})`);
        break;
      }
      bytesIn += value.byteLength;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split(/\r?\n\r?\n/);
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const trimmed = part.trim();
        if (!trimmed) continue;
        const lines = trimmed.split(/\r?\n/);
        const dataPieces: string[] = [];
        for (const line of lines) {
          if (line.startsWith(":")) continue;
          if (line.startsWith("data:")) {
            dataPieces.push(line.slice(5).replace(/^ /, ""));
          }
        }
        if (dataPieces.length === 0) continue;
        const dataLine = dataPieces.join("\n");
        let event: ChatEvent;
        try {
          event = JSON.parse(dataLine) as ChatEvent;
        } catch (err) {
          log(`bad JSON: ${dataLine.slice(0, 120)}`);
          continue;
        }
        eventsOut += 1;
        try {
          onEvent(event);
        } catch (err) {
          log(`onEvent threw: ${(err as Error).message}`);
        }
        if (event.type === "done") {
          log(`done event after ${eventsOut} events`);
          return;
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // best effort
    }
  }
}
