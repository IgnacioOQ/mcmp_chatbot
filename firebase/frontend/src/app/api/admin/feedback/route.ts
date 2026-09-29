import { callBackend } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED = (process.env.ALLOWED_ADMIN_EMAILS ?? "")
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

// The backend verifies the caller's Firebase ID token and returns its email;
// entries are passed on only if that email is on the admin allowlist.
export async function GET(req: Request) {
  const idToken = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (!idToken) return Response.json({ error: "unauthorized" }, { status: 401 });
  try {
    const data = (await callBackend("/admin/feedback", {
      method: "POST",
      body: { id_token: idToken },
    })) as { email: string; items: unknown[] };
    if (!ALLOWED.includes(data.email.toLowerCase())) {
      return Response.json({ error: "forbidden" }, { status: 403 });
    }
    return Response.json({ items: data.items });
  } catch {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
}
