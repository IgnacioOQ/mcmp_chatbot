export type Role = "user" | "assistant";

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  done?: boolean;
}

export interface Message {
  role: Role;
  content: string;
  toolCalls?: ToolCall[];
}

export interface MonthEvent {
  day: number;
  title: string;
  speaker: string;
  location?: string | null;
  description: string;
  url: string;
}

export interface WeekEvent {
  title: string;
  speaker: string;
  date: string; // ISO yyyy-mm-dd
  time: string;
  location?: string | null;
  url: string;
}

export const TOOL_ICONS: Record<string, string> = {
  search_people: "🔍",
  search_research: "📚",
  get_events: "📅",
  search_graph: "🏛️",
  grep_data: "🔎",
  fuzzy_search: "🪄",
  search_academic_offerings: "🎓",
  ask_clarification: "❓",
};

// What the placeholder bubble says while a tool runs.
export const TOOL_LABELS: Record<string, string> = {
  search_people: "Looking for people…",
  search_research: "Searching research topics…",
  get_events: "Looking for events…",
  search_graph: "Checking the MCMP's structure…",
  grep_data: "Searching the records…",
  fuzzy_search: "Searching the records…",
  search_academic_offerings: "Checking academic programs…",
  ask_clarification: "Preparing a follow-up question…",
};

// Status line for an assistant turn that has no answer text yet.
export function statusFor(m: Message): string {
  const last = m.toolCalls?.at(-1);
  if (!last) return "Leopold is thinking…";
  if (last.done) return "Writing the answer…";
  return TOOL_LABELS[last.name] ?? "Working…";
}
