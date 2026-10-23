import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Cliente de Supabase para usar en server components, route handlers y el
 * proxy (middleware). Lee y escribe la sesion a traves de las cookies de la
 * petición actual.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            for (const { name, value, options } of cookiesToSet) {
              cookieStore.set(name, value, options);
            }
          } catch {
            // Se llama desde un server component: las cookies no se pueden
            // escribir ahi. El proxy ya se encarga de refrescar la sesion.
          }
        },
      },
    },
  );
}
