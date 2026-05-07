"use client";

import { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat } from "@/lib/api";
import type { ChatEvent } from "@/lib/types";
import { Send, Loader2, Wrench, CheckCircle2, AlertCircle, Sparkles, History } from "lucide-react";

type ToolEvent = {
  kind: "tool_call" | "tool_result";
  name: string;
  detail: string;
  ts: number;
};

type Turn = {
  role: "user" | "assistant";
  content: string;
  events?: ToolEvent[];
  current?: ToolEvent | null;
  status?: string;
  error?: string;
};

export type AgentChatHandle = {
  send: (text: string) => void;
};

type Props = {
  placeholder?: string;
  greeting?: string;
};

// Backend keeps things snappy by trimming history to the last few turns.
// We mirror the cap on the client and surface it to the user via the system
// prompt so the model knows it has a finite memory.
const HISTORY_TURNS_KEPT = 2;

export const AgentChat = forwardRef<AgentChatHandle, Props>(function AgentChat(
  { placeholder = "Ask Beach, Please anything...", greeting },
  ref,
) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [showLog, setShowLog] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const turnsRef = useRef<Turn[]>([]);
  useEffect(() => {
    turnsRef.current = turns;
  }, [turns]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns, pending]);

  const log = useCallback((line: string) => {
    const stamped = `${new Date().toLocaleTimeString()}  ${line}`;
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.log("[chat]", stamped);
    }
    setLogLines((cur) => [...cur.slice(-49), stamped]);
  }, []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || pending) return;
      setInput("");
      setPending(true);

      const userTurn: Turn = { role: "user", content: trimmed };
      const assistantTurn: Turn = {
        role: "assistant",
        content: "",
        events: [],
        current: null,
        status: "Beach, Please is thinking...",
      };
      const priorTurns = turnsRef.current;

      // Keep only the last N completed user/assistant pairs so prompts stay
      // short and predictable. Most recent turns are the most useful.
      const completed = priorTurns.filter((t) => t.content && t.content.trim());
      const trimmedHistory = completed.slice(-HISTORY_TURNS_KEPT * 2);
      const history: { role: string; content: string }[] = [
        ...trimmedHistory.map((t) => ({ role: t.role, content: t.content })),
        { role: "user", content: trimmed },
      ];

      const nextTurns = [...priorTurns, userTurn, assistantTurn];
      turnsRef.current = nextTurns;
      setTurns(nextTurns);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        await streamChat(
          history,
          (event: ChatEvent) => {
            setTurns((cur) => {
              if (cur.length === 0) return cur;
              const last = cur[cur.length - 1];
              if (last.role !== "assistant") return cur;
              const next: Turn = {
                ...last,
                events: [...(last.events ?? [])],
              };
              switch (event.type) {
                case "status":
                  next.status = event.message;
                  break;
                case "tool_call": {
                  const ev: ToolEvent = {
                    kind: "tool_call",
                    name: event.name,
                    detail:
                      typeof event.arguments === "string"
                        ? event.arguments
                        : JSON.stringify(event.arguments),
                    ts: Date.now(),
                  };
                  next.events!.push(ev);
                  next.current = ev;
                  next.status = undefined;
                  break;
                }
                case "tool_result": {
                  const ev: ToolEvent = {
                    kind: "tool_result",
                    name: event.name,
                    detail: event.preview,
                    ts: Date.now(),
                  };
                  next.events!.push(ev);
                  next.current = ev;
                  next.status = undefined;
                  break;
                }
                case "delta":
                  next.content = (next.content ?? "") + event.content;
                  next.status = undefined;
                  next.current = null;
                  break;
                case "error":
                  next.error = event.message;
                  next.status = undefined;
                  next.current = null;
                  break;
                case "done":
                  next.status = undefined;
                  next.current = null;
                  break;
                default:
                  return cur;
              }
              return [...cur.slice(0, -1), next];
            });
          },
          { signal: ctrl.signal, log },
        );
      } catch (err) {
        const msg = (err as Error).message ?? "unknown error";
        log(`stream error: ${msg}`);
        setTurns((cur) => {
          if (cur.length === 0) return cur;
          const last = cur[cur.length - 1];
          if (last.role !== "assistant") return cur;
          return [
            ...cur.slice(0, -1),
            {
              ...last,
              error: msg,
              status: undefined,
              current: null,
            },
          ];
        });
      } finally {
        setPending(false);
        abortRef.current = null;
      }
    },
    [pending, log],
  );

  useImperativeHandle(ref, () => ({ send }), [send]);

  const stop = () => {
    abortRef.current?.abort();
  };

  return (
    <div className="bg-white/90 backdrop-blur rounded-3xl border border-white/60 shadow-xl flex flex-col overflow-hidden">
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-6 space-y-6 min-h-[320px] max-h-[60vh]"
      >
        {turns.length === 0 && greeting && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-coral-400 text-white flex items-center justify-center flex-shrink-0 shadow-sm">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="bg-sand-50 border border-sand-100 rounded-2xl rounded-tl-sm px-4 py-3 text-ocean-900">
              {greeting}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <Bubble key={i} turn={t} isLast={i === turns.length - 1} pending={pending} />
        ))}
      </div>

      <form
        className="border-t border-white/60 bg-white/80 px-4 py-3 flex gap-2 items-center"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          className="flex-1 bg-transparent rounded-lg px-3 py-2 text-base outline-none text-ocean-900 placeholder:text-ocean-700/50"
          disabled={pending}
          autoFocus
        />
        {pending ? (
          <button
            type="button"
            onClick={stop}
            className="bg-stone-200 hover:bg-stone-300 text-ocean-900 rounded-lg px-3 py-2 text-sm font-medium"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="bg-coral-500 hover:bg-coral-400 disabled:bg-stone-300 text-white rounded-lg px-4 py-2 flex items-center gap-1.5 font-medium"
          >
            <Send className="w-4 h-4" />
            <span>Ask</span>
          </button>
        )}
      </form>

      <div className="border-t border-white/40 px-4 py-1.5 flex items-center justify-between bg-ocean-50/60">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowLog((s) => !s)}
            className="text-[10px] font-mono text-ocean-700/70 hover:text-coral-500 uppercase tracking-wider"
          >
            {showLog ? "hide log" : "show stream log"} ({logLines.length})
          </button>
          <span className="flex items-center gap-1 text-[10px] font-mono text-ocean-700/60">
            <History className="w-3 h-3" /> last {HISTORY_TURNS_KEPT} turns kept
          </span>
        </div>
        <span className="text-[10px] font-mono text-ocean-700/60">
          {pending ? "streaming..." : "idle"}
        </span>
      </div>
      {showLog && (
        <div className="bg-ocean-900 text-emerald-300 font-mono text-[11px] px-4 py-2 max-h-40 overflow-y-auto">
          {logLines.length === 0 ? (
            <div className="text-ocean-200">No events yet.</div>
          ) : (
            logLines.map((l, i) => <div key={i}>{l}</div>)
          )}
        </div>
      )}
    </div>
  );
});

function Bubble({
  turn,
  isLast,
  pending,
}: {
  turn: Turn;
  isLast: boolean;
  pending: boolean;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-ocean-700 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[85%] shadow-sm whitespace-pre-wrap">
          {turn.content}
        </div>
      </div>
    );
  }

  const showTicker = pending && isLast && (turn.current || turn.status);
  const completedToolCount = (turn.events ?? []).filter((e) => e.kind === "tool_result").length;

  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-full bg-coral-400 text-white flex items-center justify-center flex-shrink-0 shadow-sm">
        <Sparkles className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        {showTicker && <ToolTicker turn={turn} />}

        {!pending && (turn.events?.length ?? 0) > 0 && (
          <ToolSummary count={completedToolCount} events={turn.events ?? []} />
        )}

        {turn.content && (
          <div className="bg-sand-50 border border-sand-100 text-ocean-900 rounded-2xl rounded-tl-sm px-4 py-3 leading-relaxed text-[15px]">
            <MarkdownView content={turn.content} />
            {pending && isLast && (
              <span className="inline-block w-1.5 h-4 ml-0.5 bg-ocean-700 animate-pulse align-text-bottom" />
            )}
          </div>
        )}

        {turn.error && (
          <div className="flex items-start gap-2 bg-coral-300/30 border border-coral-400/40 rounded-2xl px-4 py-3 text-sm text-coral-600">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>
              <strong className="font-semibold">Stream error.</strong> {turn.error}
              <br />
              <span className="text-xs text-ocean-700">
                Open the stream log below to see what happened.
              </span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function ToolTicker({ turn }: { turn: Turn }) {
  const ev = turn.current;
  // Use the timestamp as a key so React fully unmounts the previous ticker
  // and remounts a new one — letting the CSS keyframe restart cleanly.
  const k = ev ? `${ev.kind}-${ev.ts}` : `status-${turn.status}`;
  return (
    <div className="relative h-7 overflow-hidden">
      <div
        key={k}
        className="absolute inset-0 flex items-center gap-2 text-sm text-ocean-800 ticker-flash"
      >
        {ev ? (
          <>
            {ev.kind === "tool_call" ? (
              <Wrench className="w-3.5 h-3.5 text-coral-500 flex-shrink-0" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
            )}
            <span className="font-mono text-xs">
              <span className="font-semibold text-ocean-900">{ev.name}</span>
              <span className="text-ocean-700">
                {ev.kind === "tool_call"
                  ? ` (${truncate(ev.detail, 80)})`
                  : ` → ${truncate(ev.detail, 100)}`}
              </span>
            </span>
          </>
        ) : (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin text-ocean-700" />
            <span>{turn.status}</span>
          </>
        )}
      </div>
    </div>
  );
}

function ToolSummary({ count, events }: { count: number; events: ToolEvent[] }) {
  const [open, setOpen] = useState(false);
  if (count === 0) return null;
  const names = Array.from(new Set(events.map((e) => e.name)));
  return (
    <div className="text-[11px]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="font-mono text-ocean-700/80 hover:text-coral-500 inline-flex items-center gap-1.5"
      >
        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
        used {count} tool{count === 1 ? "" : "s"}: {names.join(", ")}
        <span className="text-ocean-700/50">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <ul className="mt-1.5 ml-4 space-y-0.5 font-mono text-ocean-700/80 border-l border-ocean-200 pl-3">
          {events.map((ev, i) => (
            <li key={i} className="break-all">
              {ev.kind === "tool_call" ? "→ " : "← "}
              <span className="font-semibold text-ocean-900">{ev.name}</span>
              {ev.kind === "tool_call" ? `(${truncate(ev.detail, 100)})` : ` ${truncate(ev.detail, 100)}`}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MarkdownView({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="my-1.5 first:mt-0 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="my-1.5 ml-4 list-disc space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="my-1.5 ml-4 list-decimal space-y-0.5">{children}</ol>,
        li: ({ children }) => <li className="leading-snug">{children}</li>,
        strong: ({ children }) => <strong className="font-semibold text-ocean-900">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        h1: ({ children }) => <h3 className="text-base font-bold mt-2 mb-1">{children}</h3>,
        h2: ({ children }) => <h3 className="text-base font-bold mt-2 mb-1">{children}</h3>,
        h3: ({ children }) => <h4 className="text-sm font-bold mt-2 mb-1">{children}</h4>,
        h4: ({ children }) => <h4 className="text-sm font-semibold mt-1.5 mb-1">{children}</h4>,
        code: ({ children }) => (
          <code className="bg-ocean-100 text-ocean-900 rounded px-1 py-0.5 text-[0.85em] font-mono">
            {children}
          </code>
        ),
        a: ({ href, children }) => (
          <a href={href} className="text-coral-600 underline" target="_blank" rel="noreferrer">
            {children}
          </a>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-coral-300 pl-3 italic text-ocean-800/90 my-1.5">
            {children}
          </blockquote>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length <= n ? s : s.slice(0, n) + "…";
}
