"use client";

import { useState } from "react";

export default function FeedbackForm() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "ok" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim()) return;
    setStatus("sending");
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, message }),
      });
      if (!res.ok) throw new Error();
      setStatus("ok");
      setName("");
      setMessage("");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="font-semibold text-sm flex items-center gap-1"
      >
        💬 Give Feedback <span className="text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <form onSubmit={submit} className="mt-2 flex flex-col gap-2">
          <input
            type="text"
            placeholder="Name (optional)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          />
          <textarea
            placeholder="Your feedback"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            className="border rounded px-2 py-1 text-sm"
          />
          <button
            type="submit"
            disabled={status === "sending"}
            className="bg-blue-600 text-white rounded px-3 py-1 text-sm disabled:opacity-50"
          >
            {status === "sending" ? "Sending…" : "Submit"}
          </button>
          {status === "ok" && <p className="text-xs text-green-600">Thank you for your feedback!</p>}
          {status === "error" && <p className="text-xs text-red-600">Something went wrong. Try again.</p>}
        </form>
      )}
    </div>
  );
}
