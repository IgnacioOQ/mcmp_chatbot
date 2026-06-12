import { initializeApp, getApps, FirebaseApp } from "firebase/app";

// Firebase web config. The API key is public-facing by design (Firebase web
// keys are not secrets). Set NEXT_PUBLIC_FB_API_KEY after registering the web
// app during firebase init (see FIREBASE_MIGRATION_PLAN.md §5.6).
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FB_API_KEY,
  authDomain: "mcmp-firebase.firebaseapp.com",
  projectId: "mcmp-firebase",
};

export const app: FirebaseApp = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
