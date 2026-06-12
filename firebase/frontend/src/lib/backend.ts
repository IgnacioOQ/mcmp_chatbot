import { GoogleAuth } from "google-auth-library";

// The Next.js server (running in App Hosting's managed Cloud Run) mints an OIDC
// identity token for the IAM-only backend on each call. The browser never holds
// backend credentials. BACKEND_URL is the Cloud Run service URL (Secret Manager).
const auth = new GoogleAuth();

export async function callBackend(
  path: string,
  init?: { method?: string; body?: unknown },
): Promise<unknown> {
  const base = process.env.BACKEND_URL;
  if (!base) throw new Error("BACKEND_URL is not set");

  const client = await auth.getIdTokenClient(base);
  const res = await client.request({
    url: `${base}${path}`,
    method: init?.method ?? "GET",
    data: init?.body,
    responseType: "json",
  });
  return res.data;
}
