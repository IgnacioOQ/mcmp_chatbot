"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import CalendarWidget from "@/components/CalendarWidget";
import EventsThisWeek from "@/components/EventsThisWeek";
import FeedbackForm from "@/components/FeedbackForm";
import { Message, TOOL_ICONS } from "@/lib/types";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Keep the latest turn in view as tool chips and text stream in.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(prompt: string) {
    if (!prompt.trim() || loading) return;
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    // Append the user turn plus an empty assistant placeholder we fill as the
    // NDJSON event stream arrives — chips first, then text.
    setMessages((m) => [
      ...m,
      { role: "user", content: prompt },
      { role: "assistant", content: "", toolCalls: [] },
    ]);
    setInput("");
    setLoading(true);

    // Mutate the in-progress assistant message (always the last one).
    const updateLast = (fn: (m: Message) => Message) =>
      setMessages((msgs) => {
        const copy = msgs.slice();
        copy[copy.length - 1] = fn(copy[copy.length - 1]);
        return copy;
      });

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: prompt, history }),
      });
      if (!res.body) throw new Error("no response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let nl: number;
        // NDJSON: one JSON event per line; the last partial line stays buffered.
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (!line) continue;
          let ev: { type: string; name?: string; args?: Record<string, unknown>; text?: string; message?: string };
          try {
            ev = JSON.parse(line);
          } catch {
            continue;
          }
          if (ev.type === "tool_call") {
            updateLast((m) => ({
              ...m,
              toolCalls: [...(m.toolCalls ?? []), { name: ev.name ?? "", args: ev.args ?? {} }],
            }));
          } else if (ev.type === "token") {
            updateLast((m) => ({ ...m, content: m.content + (ev.text ?? "") }));
          } else if (ev.type === "error") {
            updateLast((m) => ({ ...m, content: m.content + `\n\nError: ${ev.message ?? "unknown"}` }));
          }
        }
      }
      // If the turn produced no text at all, leave a visible marker.
      updateLast((m) => (m.content ? m : { ...m, content: "(no response)" }));
    } catch {
      updateLast(() => ({ role: "assistant", content: "Error contacting the server." }));
    } finally {
      setLoading(false);
    }
  }

  function onCalendarPick(formatted: string) {
    send(
      `What talks or events are scheduled for ${formatted}? Please provide details about each event, including an abstract or description.`,
    );
  }

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen">
      {/* Sidebar */}
      <aside className="w-full md:w-[560px] shrink-0 border-r border-gray-200 p-4 space-y-4 bg-gray-50 md:overflow-y-auto">
        <CalendarWidget onPick={onCalendarPick} />
        <hr />
        <FeedbackForm />
        <hr />
        <EventsThisWeek />
      </aside>

      {/* Main chat */}
      <main className="flex-1 flex flex-col p-4 max-w-3xl mx-auto w-full md:overflow-hidden">
        <h1 className="text-4xl font-bold mb-1">Leopold: The MCMP Chatbot</h1>
        <p className="text-lg text-gray-600 mb-4">
          Ask about talks, speakers, people, research, and academic programs at the Munich
          Center for Mathematical Philosophy. Click a calendar day to see that day&apos;s events.
        </p>

        <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border border-green-600 p-4">
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
              {m.role === "assistant" && m.toolCalls && m.toolCalls.length > 0 && (
                <div className="text-xs text-gray-500 mb-1">
                  {m.toolCalls.map((tc, j) => (
                    <span key={j} className="mr-2">
                      {TOOL_ICONS[tc.name] ?? "⚙️"} {tc.name}
                    </span>
                  ))}
                </div>
              )}
              <div
                className={
                  "inline-block rounded-lg px-3 py-2 text-left " +
                  (m.role === "user" ? "bg-brand text-white" : "bg-gray-100 text-gray-900")
                }
              >
                {m.role === "assistant" ? (
                  m.content ? (
                    <div className="prose prose-sm max-w-none">
                      <ReactMarkdown
                        components={{
                          a: (props) => (
                            <a
                              {...props}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 underline hover:text-blue-800"
                            />
                          ),
                        }}
                      >
                        {m.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <span className="text-gray-500">Leopold is thinking…</span>
                  )
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="mt-4 flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="What is the next talk about?"
            className="flex-1 border rounded px-3 py-2"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-brand text-white rounded px-4 py-2 disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
