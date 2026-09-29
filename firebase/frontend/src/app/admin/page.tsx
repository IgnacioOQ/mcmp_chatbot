"use client";

import { useEffect, useState } from "react";
import { app } from "@/lib/firebase";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  signOut,
  onAuthStateChanged,
  User,
} from "firebase/auth";

const ALLOWED = (process.env.NEXT_PUBLIC_ALLOWED_ADMIN_EMAILS ?? "")
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

type Feedback = { timestamp: string; name: string; message: string };

export default function Admin() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [scrapeStatus, setScrapeStatus] = useState("");
  const [feedback, setFeedback] = useState<Feedback[] | null>(null);

  useEffect(() => {
    const auth = getAuth(app);
    return onAuthStateChanged(auth, (u) => {
      setUser(u);
      setChecked(true);
    });
  }, []);

  async function login() {
    const auth = getAuth(app);
    try {
      await signInWithPopup(auth, new GoogleAuthProvider());
    } catch {
      // Popup blocked (common on mobile) → fall back to redirect.
      await signInWithRedirect(auth, new GoogleAuthProvider());
    }
  }

  async function logout() {
    await signOut(getAuth(app));
  }

  async function loadFeedback() {
    if (!user) return;
    try {
      const r = await fetch("/api/admin/feedback", {
        headers: { Authorization: `Bearer ${await user.getIdToken()}` },
      });
      setFeedback(r.ok ? (await r.json()).items : []);
    } catch {
      setFeedback([]);
    }
  }

  async function triggerScrape() {
    setScrapeStatus("Starting…");
    try {
      const r = await fetch("/api/admin/scrape", { method: "POST" });
      const d = await r.json();
      setScrapeStatus(`Status: ${d.status}${d.code ? ` (${d.code})` : ""}`);
    } catch {
      setScrapeStatus("Failed to start scrape.");
    }
  }

  const email = (user?.email ?? "").toLowerCase();
  const allowed = !!user && (ALLOWED.length === 0 || ALLOWED.includes(email));

  useEffect(() => {
    if (allowed) loadFeedback();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowed]);

  return (
    <main className="max-w-xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-4">MCMP Admin</h1>

      {!checked && <p className="text-gray-500">Loading…</p>}

      {checked && !user && (
        <button onClick={login} className="bg-brand text-white rounded px-4 py-2">
          Sign in with Google
        </button>
      )}

      {checked && user && !allowed && (
        <div>
          <p className="text-red-600 mb-3">
            {email} is not authorized for the admin panel.
          </p>
          <button onClick={logout} className="text-sm underline">Sign out</button>
        </div>
      )}

      {checked && allowed && (
        <div className="space-y-4">
          <p className="text-sm text-gray-600">Signed in as {email}</p>
          <div className="flex flex-col gap-2 items-start">
            <button onClick={triggerScrape} className="bg-brand text-white rounded px-4 py-2">
              Trigger Scrape
            </button>
            {scrapeStatus && <p className="text-sm text-gray-700">{scrapeStatus}</p>}
          </div>
          <section>
            <h2 className="text-lg font-semibold mb-2">Feedback</h2>
            {feedback === null && <p className="text-sm text-gray-500">Loading…</p>}
            {feedback?.length === 0 && <p className="text-sm text-gray-500">No feedback yet.</p>}
            <ul className="space-y-2">
              {feedback?.map((f, i) => (
                <li key={i} className="border rounded p-2 text-sm">
                  <p className="text-gray-500 text-xs">
                    {new Date(f.timestamp).toLocaleString()}{f.name ? ` — ${f.name}` : ""}
                  </p>
                  <p className="whitespace-pre-wrap">{f.message}</p>
                </li>
              ))}
            </ul>
          </section>
          <button onClick={logout} className="text-sm underline">Sign out</button>
        </div>
      )}
    </main>
  );
}
