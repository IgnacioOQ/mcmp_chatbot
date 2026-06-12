"use client";

import { useEffect, useState, useCallback } from "react";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];

function buildWeeks(year: number, month: number): number[][] {
  // month is 1-12. Monday-first grid.
  const first = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const startDow = (first.getDay() + 6) % 7; // 0 = Monday
  const weeks: number[][] = [];
  let week: number[] = new Array(startDow).fill(0);
  for (let d = 1; d <= daysInMonth; d++) {
    week.push(d);
    if (week.length === 7) {
      weeks.push(week);
      week = [];
    }
  }
  if (week.length) {
    while (week.length < 7) week.push(0);
    weeks.push(week);
  }
  return weeks;
}

export default function CalendarWidget({
  onPick,
}: {
  onPick: (formatted: string) => void;
}) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1); // 1-12
  const [eventDays, setEventDays] = useState<number[]>([]);

  const today = new Date();
  const isCurrentMonth =
    today.getFullYear() === year && today.getMonth() + 1 === month;

  const loadEventDays = useCallback(async () => {
    try {
      const res = await fetch("/api/events/month", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ year, month }),
      });
      const data = await res.json();
      setEventDays(Array.isArray(data?.event_days) ? data.event_days : []);
    } catch {
      setEventDays([]);
    }
  }, [year, month]);

  useEffect(() => {
    loadEventDays();
  }, [loadEventDays]);

  function prev() {
    if (month === 1) {
      setMonth(12);
      setYear((y) => y - 1);
    } else {
      setMonth((m) => m - 1);
    }
  }
  function next() {
    if (month === 12) {
      setMonth(1);
      setYear((y) => y + 1);
    } else {
      setMonth((m) => m + 1);
    }
  }

  const weeks = buildWeeks(year, month);

  return (
    <div className="text-sm">
      <div className="flex items-center justify-between mb-2">
        <button onClick={prev} className="px-2 py-1 rounded hover:bg-gray-200" aria-label="Previous month">◀</button>
        <h4 className="font-semibold">{MONTHS[month - 1]} {year}</h4>
        <button onClick={next} className="px-2 py-1 rounded hover:bg-gray-200" aria-label="Next month">▶</button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-gray-500 mb-1">
        {WEEKDAYS.map((d, i) => (
          <div key={i}>{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {weeks.flat().map((day, i) => {
          if (day === 0) return <div key={i} className="h-9" />;
          const isToday = isCurrentMonth && day === today.getDate();
          const hasEvent = eventDays.includes(day);
          const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const formatted = `${MONTHS[month - 1]} ${day}, ${year}`;
          return (
            <button
              key={i}
              data-iso={iso}
              onClick={() => onPick(formatted)}
              className={
                "h-9 rounded flex flex-col items-center justify-center leading-none " +
                (isToday ? "bg-blue-600 text-white" : "hover:bg-gray-200")
              }
            >
              <span>{day}</span>
              {hasEvent && (
                <span className={isToday ? "text-white text-[10px]" : "text-blue-500 text-[10px]"}>●</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
