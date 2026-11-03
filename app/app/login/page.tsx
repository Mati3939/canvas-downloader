"use client";

import Link from "next/link";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function entrarConGoogle() {
    setError(null);
    setCargando(true);
    const supabase = createClient();
    const { error: errorOAuth } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (errorOAuth) {
      setError("No se pudo iniciar el login. Intenta de nuevo.");
      setCargando(false);
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 bg-zinc-50 px-6 dark:bg-black">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Better Canvas
        </h1>
        <p className="max-w-xs text-sm text-zinc-500 dark:text-zinc-400">
          Inicia sesion con tu cuenta de Google para ver tus ramos.
        </p>
      </div>

      <button
        type="button"
        onClick={entrarConGoogle}
        disabled={cargando}
        className="flex w-full max-w-xs items-center justify-center gap-3 rounded-full border border-zinc-300 bg-white px-5 py-3 text-sm font-medium text-zinc-900 shadow-sm transition-colors hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50 dark:hover:bg-zinc-800"
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5">
          <path
            fill="#4285F4"
            d="M23.52 12.27c0-.85-.08-1.67-.21-2.45H12v4.64h6.46a5.52 5.52 0 0 1-2.4 3.62v3.01h3.86c2.26-2.08 3.6-5.15 3.6-8.82Z"
          />
          <path
            fill="#34A853"
            d="M12 24c3.24 0 5.95-1.07 7.93-2.91l-3.86-3.01c-1.07.72-2.45 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.95H1.27v3.1A11.99 11.99 0 0 0 12 24Z"
          />
          <path
            fill="#FBBC05"
            d="M5.27 14.28A7.14 7.14 0 0 1 4.89 12c0-.79.14-1.56.38-2.28V6.62H1.27A11.99 11.99 0 0 0 0 12c0 1.93.46 3.76 1.27 5.38l4-3.1Z"
          />
          <path
            fill="#EA4335"
            d="M12 4.77c1.77 0 3.35.61 4.6 1.8l3.42-3.42A11.9 11.9 0 0 0 12 0 11.99 11.99 0 0 0 1.27 6.62l4 3.1C6.22 6.88 8.87 4.77 12 4.77Z"
          />
        </svg>
        {cargando ? "Entrando..." : "Entrar con Google"}
      </button>

      {error ? (
        <p className="max-w-xs text-center text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}

      <nav className="flex gap-4 text-xs text-zinc-500 dark:text-zinc-400">
        <Link href="/acerca" className="underline">
          Acerca de
        </Link>
        <Link href="/privacidad" className="underline">
          Privacidad
        </Link>
      </nav>
    </main>
  );
}
