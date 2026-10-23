import Link from "next/link";
import { notFound } from "next/navigation";
import { FilaArchivo } from "@/components/FilaArchivo";
import { ListaModulos } from "@/components/ListaModulos";
import { Novedad } from "@/components/Novedad";
import { agruparMaterial } from "@/lib/material";
import {
  armarNovedades,
  type AnuncioParaNovedades,
  type TareaParaNovedades,
} from "@/lib/novedades";
import { createClient } from "@/lib/supabase/server";
import type { Archivo, Curso } from "@/lib/tipos";

const DIAS_LO_NUEVO = 30;
const MS_POR_DIA = 24 * 60 * 60 * 1000;

const COLUMNAS_CURSO = "canvas_id, name, role, canvas_url, drive_url";
const COLUMNAS_ANUNCIOS =
  "canvas_id, course_id, title, posted_at, canvas_url, attachment_ids, inicial";
const COLUMNAS_TAREAS =
  "canvas_id, course_id, name, canvas_url, inicial, first_seen_at";
const COLUMNAS_MODULOS = "canvas_id, name, position";
const COLUMNAS_ITEMS =
  "canvas_id, module_id, position, title, type, file_id, external_url, canvas_url";

type Pestana = "nuevo" | "material" | "modulos";
const PESTANAS: { valor: Pestana; etiqueta: string }[] = [
  { valor: "nuevo", etiqueta: "Lo nuevo" },
  { valor: "material", etiqueta: "Material" },
  { valor: "modulos", etiqueta: "Modulos" },
];

function esPestana(valor: string | undefined): valor is Pestana {
  return valor === "nuevo" || valor === "material" || valor === "modulos";
}

function MensajeError() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-2 bg-zinc-50 px-6 text-center dark:bg-black">
      <p className="text-sm text-red-600 dark:text-red-400">
        No se pudo cargar la informacion de este ramo. Intenta de nuevo mas
        tarde.
      </p>
    </main>
  );
}

export default async function PaginaRamo({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { id } = await params;
  const cursoId = Number(id);
  if (!Number.isInteger(cursoId) || id.trim() === "") {
    notFound();
  }

  const { tab } = await searchParams;
  const pestana: Pestana = esPestana(tab) ? tab : "nuevo";

  const supabase = await createClient();
  const ahora = new Date();
  const desde = new Date(ahora.getTime() - DIAS_LO_NUEVO * MS_POR_DIA);

  const [cursoRes, anunciosRes, tareasRes, archivosRes, modulosRes, itemsRes] =
    await Promise.all([
      supabase
        .from("courses")
        .select(COLUMNAS_CURSO)
        .eq("canvas_id", cursoId)
        .maybeSingle(),
      supabase
        .from("announcements")
        .select(COLUMNAS_ANUNCIOS)
        .eq("course_id", cursoId)
        .eq("inicial", false),
      supabase
        .from("assignments")
        .select(COLUMNAS_TAREAS)
        .eq("course_id", cursoId)
        .eq("inicial", false),
      supabase.from("files").select("*").eq("course_id", cursoId),
      supabase
        .from("modules")
        .select(COLUMNAS_MODULOS)
        .eq("course_id", cursoId)
        .order("position", { ascending: true }),
      supabase
        .from("module_items")
        .select(COLUMNAS_ITEMS)
        .eq("course_id", cursoId)
        .order("position", { ascending: true }),
    ]);

  if (cursoRes.error || !cursoRes.data) {
    notFound();
  }

  const error =
    anunciosRes.error ?? tareasRes.error ?? archivosRes.error ?? modulosRes.error ?? itemsRes.error;

  if (error) {
    return <MensajeError />;
  }

  const curso = cursoRes.data as Pick<
    Curso,
    "canvas_id" | "name" | "role" | "canvas_url" | "drive_url"
  >;
  const anuncios = (anunciosRes.data ?? []) as AnuncioParaNovedades[];
  const tareas = (tareasRes.data ?? []) as TareaParaNovedades[];
  const archivos = (archivosRes.data ?? []) as Archivo[];
  const modulos = modulosRes.data ?? [];
  const items = itemsRes.data ?? [];

  const novedades = armarNovedades(anuncios, tareas, archivos, desde);
  const grupos = agruparMaterial(archivos);
  const archivosPorId = new Map(archivos.map((a) => [a.canvas_id, a]));

  return (
    <main className="flex flex-1 flex-col gap-6 bg-zinc-50 px-4 py-6 dark:bg-black">
      <header className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            {curso.name}
          </h1>
          {curso.role === "ta" ? (
            <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
              Ayudante
            </span>
          ) : null}
        </div>
        <div className="flex gap-4 text-sm">
          {curso.drive_url ? (
            <a
              href={curso.drive_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-zinc-700 underline-offset-2 hover:underline dark:text-zinc-300"
            >
              Carpeta en Drive
            </a>
          ) : null}
          <a
            href={curso.canvas_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-zinc-700 underline-offset-2 hover:underline dark:text-zinc-300"
          >
            Ver en Canvas
          </a>
        </div>
      </header>

      <nav className="flex gap-1 border-b border-zinc-200 dark:border-zinc-800">
        {PESTANAS.map((p) => (
          <Link
            key={p.valor}
            href={p.valor === "nuevo" ? "?" : `?tab=${p.valor}`}
            className={
              p.valor === pestana
                ? "border-b-2 border-zinc-900 px-3 py-2 text-sm font-semibold text-zinc-900 dark:border-zinc-50 dark:text-zinc-50"
                : "border-b-2 border-transparent px-3 py-2 text-sm text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
            }
          >
            {p.etiqueta}
          </Link>
        ))}
      </nav>

      {pestana === "nuevo" ? (
        novedades.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            No hay nada nuevo en los ultimos {DIAS_LO_NUEVO} dias.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {novedades.map((novedad) => (
              <Novedad
                key={`${novedad.tipo}-${novedad.id}`}
                novedad={novedad}
                nombreRamo={curso.name}
                ahora={ahora}
              />
            ))}
          </ul>
        )
      ) : null}

      {pestana === "material" ? (
        grupos.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Todavia no hay material sincronizado de este ramo.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {grupos.map((grupo) => (
              <details
                key={`${grupo.source}-${grupo.etiqueta}`}
                open
                className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <summary className="cursor-pointer text-sm font-semibold text-zinc-900 dark:text-zinc-50">
                  {grupo.etiqueta}
                </summary>
                <ul className="mt-2">
                  {grupo.archivos.map((archivo) => (
                    <FilaArchivo key={archivo.canvas_id} archivo={archivo} />
                  ))}
                </ul>
              </details>
            ))}
          </div>
        )
      ) : null}

      {pestana === "modulos" ? (
        <ListaModulos modulos={modulos} items={items} archivosPorId={archivosPorId} />
      ) : null}
    </main>
  );
}
