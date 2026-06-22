"use client";

import { useEffect, useState } from "react";
import type { WeekEvent } from "@/lib/types";

function formatDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long", day: "2-digit" });
}

export default function EventsThisWeek() {
  const [events, setEvents] = useState<WeekEvent[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/events/week")
      .then((r) => r.json())
      .then((data) => setEvents(Array.isArray(data) ? data : []))
      .catch(() => setError(true));
  }, []);

  return (
    <div>
      <h3 className="font-semibold mb-2">📆 Events this Week</h3>
      {error && <p className="text-sm text-red-600">Could not load events.</p>}
      {!error && events === null && <p className="text-sm text-gray-500">Loading…</p>}
      {!error && events !== null && events.length === 0 && (
        <p className="text-sm text-gray-500">No events scheduled for this week.</p>
      )}
      {!error &&
        events?.map((ev, i) => (
          <div key={i} className="mb-3 border-b border-gray-200 pb-2">
            <div className="font-semibold text-sm">{ev.speaker}</div>
            <a href={ev.url} target="_blank" rel="noopener noreferrer" className="text-sm text-brand hover:underline">
              {ev.title}
            </a>
            <div className="text-xs text-gray-500 mt-1">
              📅 {formatDate(ev.date)} at {ev.time}
              {ev.location ? ` · 📍 ${ev.location}` : ""}
            </div>
          </div>
        ))}
    </div>
  );
}
