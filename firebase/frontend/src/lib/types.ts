export type Role = "user" | "assistant";

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface Message {
  role: Role;
  content: string;
  toolCalls?: ToolCall[];
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
  search_academic_offerings: "🎓",
  ask_clarification: "❓",
};
