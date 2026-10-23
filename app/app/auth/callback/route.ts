import { NextResponse } from "next/server";
import { rutaSegura } from "@/lib/redireccion";
import { createClient } from "@/lib/supabase/server";

/**
 * Intercambia el code de OAuth por una sesion y vuelve a la pagina
 * principal (o a la ruta pedida con ?next=, validada con rutaSegura para
 * que no se pueda usar para redirigir fuera del sitio).
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = rutaSegura(searchParams.get("next"));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  return NextResponse.redirect(`${origin}/login`);
}
