import { callBackend } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Events change at most weekly (see the scrape routine), so let the CDN serve a
// cached week for 10 min and revalidate in the background for up to a day.
const CACHE_CONTROL = "public, s-maxage=600, stale-while-revalidate=86400";

export async function GET() {
  const data = await callBackend("/events/week");
  return Response.json(data, { headers: { "Cache-Control": CACHE_CONTROL } });
}
