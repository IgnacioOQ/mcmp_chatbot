import { Readable } from "node:stream";
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

// Streaming variant: proxies a backend response body through to the caller as a
// web ReadableStream (e.g. the NDJSON event stream from /chat). The OIDC client
// returns a Node Readable when responseType is "stream"; we adapt it to the web
// stream a Next.js Response expects.
export async function callBackendStream(
  path: string,
  init?: { method?: string; body?: unknown },
): Promise<ReadableStream<Uint8Array>> {
  const base = process.env.BACKEND_URL;
  if (!base) throw new Error("BACKEND_URL is not set");

  if (!clientPromise) clientPromise = auth.getIdTokenClient(base);
  const client = await clientPromise;
  const res = await client.request({
    url: `${base}${path}`,
    method: init?.method ?? "GET",
    data: init?.body,
    responseType: "stream",
  });
  return Readable.toWeb(res.data as Readable) as ReadableStream<Uint8Array>;
}
