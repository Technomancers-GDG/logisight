import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect, signOut, onAuthStateChanged } from "firebase/auth";

const firebaseConfig = {
  apiKey: (import.meta.env.VITE_FIREBASE_API_KEY || "").trim(),
  authDomain: (import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "").trim(),
  projectId: (import.meta.env.VITE_FIREBASE_PROJECT_ID || "").trim(),
  storageBucket: (import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "").trim(),
  messagingSenderId: (import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "").trim(),
  appId: (import.meta.env.VITE_FIREBASE_APP_ID || "").trim(),
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

export async function signInWithGoogle() {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const idToken = await result.user.getIdToken();
    return { user: result.user, idToken, mode: "popup" };
  } catch (error) {
    const message = String(error?.message || error || "");
    const code = String(error?.code || "");
    const shouldRedirect =
      code === "auth/popup-blocked" ||
      code === "auth/popup-closed-by-user" ||
      code === "auth/cancelled-popup-request" ||
      /cross-origin-opener-policy|window\.closed/i.test(message);

    if (shouldRedirect) {
      await signInWithRedirect(auth, googleProvider);
      return { mode: "redirect" };
    }

    console.error("Google Sign-In error:", error);
    throw error;
  }
}

export async function logout() {
  return signOut(auth);
}

export function onAuthChange(callback) {
  return onAuthStateChanged(auth, callback);
}
