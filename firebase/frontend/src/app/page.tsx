"use client";

import { useRef, useState } from "react";
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

  async function send(prompt: string) {
    if (!prompt.trim() || loading) return;
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: prompt }]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: prompt, history }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data?.response ?? "(no response)",
          toolCalls: data?.tool_calls ?? [],
        },
      ]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Error contacting the server." }]);
    } finally {
      setLoading(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  function onCalendarPick(formatted: string) {
    send(
      `What talks or events are scheduled for ${formatted}? Please provide details about each event, including an abstract or description.`,
    );
  }

  return (
    <div className="flex flex-col md:flex-row min-h-screen">
      {/* Sidebar */}
      <aside className="w-full md:w-80 shrink-0 border-r border-gray-200 p-4 space-y-4 bg-gray-50">
        <CalendarWidget onPick={onCalendarPick} />
        <hr />
        <FeedbackForm />
        <hr />
        <EventsThisWeek />
      </aside>

      {/* Main chat */}
      <main className="flex-1 flex flex-col p-4 max-w-3xl mx-auto w-full">
        <h1 className="text-2xl font-bold mb-1">Leopold — The MCMP Chatbot</h1>
        <p className="text-sm text-gray-600 mb-4">
          Ask about talks, speakers, people, research, and academic programs at the Munich
          Center for Mathematical Philosophy. Click a calendar day to see that day&apos;s events.
        </p>

        <div className="flex-1 space-y-4 overflow-y-auto">
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
                  (m.role === "user" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900")
                }
              >
                {m.role === "assistant" ? (
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))}
          {loading && <div className="text-sm text-gray-500">Leopold is thinking…</div>}
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
            className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
