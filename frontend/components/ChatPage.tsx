"use client";

import { useRef } from "react";
import { AgentChat, type AgentChatHandle } from "./AgentChat";
import type { Beach } from "@/lib/types";
import { Sparkles } from "lucide-react";

const STARTER_PROMPTS = [
  "Find me the safest beach near LA for a 3-year-old this Saturday morning.",
  "Should I surf Pismo Beach in California this weekend?",
  "Which Florida beach has the best shells right now?",
  "Compare Huntington and La Jolla for tomorrow morning.",
  "What about La Push Washington — any current rip current advisories?",
  "Should I swim at Ocean Beach SF in February? Be honest.",
];

export function ChatPage({ featured }: { featured: Beach[] }) {
  const chatRef = useRef<AgentChatHandle>(null);

  const ask = (prompt: string) => {
    chatRef.current?.send(prompt);
  };

  return (
    <main className="min-h-screen px-4 py-8 md:px-8 max-w-5xl mx-auto">
      <header className="mb-8 text-center">
        <div className="flex items-baseline gap-3 justify-center flex-wrap">
          <h1 className="text-5xl md:text-7xl font-black tracking-tight text-ocean-900">
            Beach,
          </h1>
          <h1 className="text-5xl md:text-7xl font-black tracking-tight text-coral-500 italic">
            Please.
          </h1>
        </div>
        <p className="mt-3 text-base md:text-lg text-ocean-800 max-w-2xl mx-auto">
          A sassy AI concierge that aggregates real beach data — waves, rip
          currents, NWS alerts, tides, water quality, sharks, amenities — for
          any US beach. Live. Not canned.
        </p>
      </header>

      <section className="mb-6">
        <AgentChat
          ref={chatRef}
          placeholder="Ask Beach, Please anything... or click a beach below."
          greeting={
            "Hi. I'm Beach, Please. Tell me a beach name (any US beach — I'll geocode it live if I haven't met it before), or ask me to compare a few. I pull live waves, rip currents, alerts, tides, and amenities, then tell you what I think with attitude."
          }
        />
      </section>

      <section className="mb-8">
        <h2 className="text-xs font-bold uppercase tracking-wider text-ocean-700 mb-3 flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5" />
          Try asking
        </h2>
        <div className="flex flex-wrap gap-2">
          {STARTER_PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => ask(p)}
              className="text-left text-sm bg-white/80 hover:bg-white border border-white/60 hover:border-coral-300 transition rounded-full px-4 py-2 text-ocean-800 shadow-sm"
            >
              {p}
            </button>
          ))}
        </div>
      </section>

      {featured.length > 0 && (
        <section className="mb-12">
          <h2 className="text-xs font-bold uppercase tracking-wider text-ocean-700 mb-3">
            Featured beaches (curated catalog · click for a live report)
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {featured.map((b) => (
              <button
                key={b.slug}
                onClick={() => ask(`Give me a full live report on ${b.name} (${b.state}) right now. Are conditions good?`)}
                className="text-left bg-white/70 hover:bg-white/95 border border-white/60 hover:border-coral-300 transition rounded-2xl p-4 shadow-sm hover:shadow-md"
              >
                <div className="flex items-baseline justify-between gap-2 mb-1">
                  <h3 className="font-semibold text-ocean-900">{b.name}</h3>
                  <span className="text-[10px] font-mono text-ocean-700">{b.state}</span>
                </div>
                <p className="text-xs text-ocean-700 mb-1.5">{b.region}</p>
                {b.description && (
                  <p className="text-xs text-ocean-800/80 line-clamp-2">{b.description}</p>
                )}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="mb-8">
        <h2 className="text-xs font-bold uppercase tracking-wider text-ocean-700 mb-3">
          Beyond the catalog
        </h2>
        <p className="text-sm text-ocean-800/90 max-w-3xl">
          Featured beaches are just suggestions. Ask about <em>any</em> US
          beach and the agent will geocode it live via OpenStreetMap, find the
          nearest NOAA tide station automatically, then pull every other
          signal from the same upstream APIs. Pismo, Surfside, Stinson,
          Wrightsville, La Push, your favorite hidden cove — try it.
        </p>
      </section>

      <footer className="text-center text-xs text-ocean-700/70 mt-12">
        Data: NOAA NWS · Open-Meteo Marine · NOAA CO-OPS · FL DOH ·
        OpenStreetMap · GSAF. Demo only — always check posted signs and
        lifeguards.
      </footer>
    </main>
  );
}
