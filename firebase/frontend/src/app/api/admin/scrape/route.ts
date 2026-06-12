import { callBackend } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// NOTE: v1 forwards to the backend, which triggers the scraper Cloud Run Job.
// Server-side verification of the caller's Firebase ID token against the admin
// allowlist is a hardening follow-up (see FIREBASE_MIGRATION_PLAN.md §5.6).
export async function POST() {
  const data = await callBackend("/admin/scrape", { method: "POST", body: {} });
  return Response.json(data);
}
