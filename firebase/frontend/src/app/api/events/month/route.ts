import { callBackend } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Events change at most weekly (see the scrape routine), so let the CDN serve a
// cached month for 10 min and revalidate in the background for up to a day.
const CACHE_CONTROL = "public, s-maxage=600, stale-while-revalidate=86400";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const year = searchParams.get("year");
  const month = searchParams.get("month");
  const data = await callBackend(`/events/month?year=${year}&month=${month}`);
  return Response.json(data, { headers: { "Cache-Control": CACHE_CONTROL } });
}
