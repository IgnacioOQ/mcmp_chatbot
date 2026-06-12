import { callBackend } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.json();
  const data = await callBackend("/feedback", { method: "POST", body });
  return Response.json(data);
}
