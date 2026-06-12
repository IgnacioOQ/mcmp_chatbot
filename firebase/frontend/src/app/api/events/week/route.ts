import { callBackend } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const data = await callBackend("/events/week");
  return Response.json(data);
}
