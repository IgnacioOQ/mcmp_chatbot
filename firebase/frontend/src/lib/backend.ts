import { GoogleAuth, IdTokenClient } from "google-auth-library";

// The Next.js server (running in App Hosting's managed Cloud Run) mints an OIDC
// identity token for the IAM-only backend. The browser never holds backend
// credentials. BACKEND_URL is the Cloud Run service URL (Secret Manager).
const auth = new GoogleAuth();

// Build the id-token client once and reuse it across requests — getIdTokenClient
// does discovery/credential work, and the client refreshes the (audience-scoped)
// token internally, so re-creating it per call just adds latency.
let clientPromise: Promise<IdTokenClient> | null = null;

export async function callBackend(
  path: string,
  init?: { method?: string; body?: unknown },
): Promise<unknown> {
  const base = process.env.BACKEND_URL;
  if (!base) throw new Error("BACKEND_URL is not set");

  if (!clientPromise) clientPromise = auth.getIdTokenClient(base);
  const client = await clientPromise;
  const res = await client.request({
    url: `${base}${path}`,
    method: init?.method ?? "GET",
    data: init?.body,
    responseType: "json",
  });
  return res.data;
}
