import { notFound } from "next/navigation";
import { Encabezado } from "@/components/Encabezado";
import { EnlaceVolver } from "@/components/EnlaceVolver";
import {
  COLUMNAS_ANUNCIO_RESUMEN,
  FilaAnuncio,
  type AnuncioResumen,
} from "@/components/FilaAnuncio";
import { FilaArchivo } from "@/components/FilaArchivo";
import { FilaTarea } from "@/components/FilaTarea";
import {
  ListaModulos,
  type ItemModuloResumen,
  type ModuloResumen,
} from "@/components/ListaModulos";
import { MensajeError } from "@/components/MensajeError";
import { PestanasRamo } from "@/components/PestanasRamo";
import { Novedad } from "@/components/Novedad";
import { colorRamo } from "@/lib/colores";
import { MS_POR_DIA } from "@/lib/fechas";
import { agruparMaterial } from "@/lib/material";
import {
  armarNovedades,
  COLUMNAS_ANUNCIO_PARA_NOVEDADES,
  COLUMNAS_TAREA_PARA_NOVEDADES,
  type AnuncioParaNovedades,
  type TareaParaNovedades,
} from "@/lib/novedades";
import { createClient } from "@/lib/supabase/server";
import {
  COLUMNAS_TAREA_RESUMEN,
  ordenarTareas,
  type TareaResumen,
} from "@/lib/tareas";
import type { Archivo, Curso } from "@/lib/tipos";

const DIAS_LO_NUEVO = 30;
const MENSAJE_ERROR =
  "No se pudo cargar la informacion de este ramo. Intenta de nuevo mas tarde.";

const COLUMNAS_CURSO = "canvas_id, name, role, canvas_url, drive_url, position";
const COLUMNAS_MODULOS = "canvas_id, name, position";
const COLUMNAS_ITEMS =
  "canvas_id, module_id, position, title, type, file_id, external_url, canvas_url";

const PESTANAS = [
  { valor: "nuevo", etiqueta: "Lo nuevo" },
  { valor: "anuncios", etiqueta: "Anuncios" },
  { valor: "tareas", etiqueta: "Tareas" },
  { valor: "material", etiqueta: "Material" },
  { valor: "modulos", etiqueta: "Modulos" },
] as const;
type Pestana = (typeof PESTANAS)[number]["valor"];

function esPestana(valor: string | undefined): valor is Pestana {
  return PESTANAS.some((p) => p.valor === valor);
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

  const [
    cursoRes,
    anunciosRes,
    tareasRes,
    archivosRes,
    modulosRes,
    itemsRes,
    todosAnunciosRes,
    todasTareasRes,
  ] = await Promise.all([
    supabase
      .from("courses")
      .select(COLUMNAS_CURSO)
      .eq("canvas_id", cursoId)
      .maybeSingle(),
    supabase
      .from("announcements")
      .select(COLUMNAS_ANUNCIO_PARA_NOVEDADES)
      .eq("course_id", cursoId)
      .eq("inicial", false),
    supabase
      .from("assignments")
      .select(COLUMNAS_TAREA_PARA_NOVEDADES)
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
    supabase
      .from("announcements")
      .select(COLUMNAS_ANUNCIO_RESUMEN)
      .eq("course_id", cursoId)
      .order("posted_at", { ascending: false }),
    supabase
      .from("assignments")
      .select(COLUMNAS_TAREA_RESUMEN)
      .eq("course_id", cursoId),
  ]);

  if (cursoRes.error) {
    console.error(
      "Error de Supabase cargando el ramo:",
      cursoRes.error.message,
    );
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }

  if (!cursoRes.data) {
    notFound();
  }

  const error =
    anunciosRes.error ??
    tareasRes.error ??
    archivosRes.error ??
    modulosRes.error ??
    itemsRes.error ??
    todosAnunciosRes.error ??
    todasTareasRes.error;

  if (error) {
    console.error("Error de Supabase cargando el ramo:", error.message);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }

  const curso = cursoRes.data as Pick<
    Curso,
    "canvas_id" | "name" | "role" | "canvas_url" | "drive_url" | "position"
  >;
  const color = colorRamo(curso);
  const anuncios = (anunciosRes.data ?? []) as AnuncioParaNovedades[];
  const tareas = (tareasRes.data ?? []) as TareaParaNovedades[];
  const archivos = (archivosRes.data ?? []) as Archivo[];
  const modulos = (modulosRes.data ?? []) as ModuloResumen[];
  const items = (itemsRes.data ?? []) as ItemModuloResumen[];
  const todosAnuncios = (todosAnunciosRes.data ?? []) as AnuncioResumen[];
  const tareasOrdenadas = ordenarTareas(
    (todasTareasRes.data ?? []) as TareaResumen[],
    ahora,
  );

  const novedades = armarNovedades(anuncios, tareas, archivos, desde);
  const grupos = agruparMaterial(archivos);
  const archivosPorId = new Map(archivos.map((a) => [a.canvas_id, a]));

  return (
    <>
      <Encabezado />
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-6 lg:px-8 lg:py-8">
        <EnlaceVolver href="/" texto="Inicio" />
        <header
          className="flex flex-col gap-3 border-l-4 pl-3"
          style={{ borderColor: color }}
        >
          <div className="flex items-start justify-between gap-2">
            <h1 className="text-xl font-semibold text-texto lg:text-2xl">
              {curso.name}
            </h1>
            {curso.role === "ta" ? (
              <span className="shrink-0 rounded-full bg-aviso-suave px-2 py-0.5 text-xs font-medium text-aviso">
                Ayudante
              </span>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {curso.drive_url ? (
              <a
                href={curso.drive_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-full border border-borde bg-superficie px-3 py-1.5 text-xs font-medium text-texto transition-colors hover:border-borde-fuerte hover:bg-superficie-2"
              >
                Carpeta en Drive
              </a>
            ) : null}
            <a
              href={curso.canvas_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center rounded-full border border-borde bg-superficie px-3 py-1.5 text-xs font-medium text-texto transition-colors hover:border-borde-fuerte hover:bg-superficie-2"
            >
              Ver en Canvas
            </a>
          </div>
        </header>

        <PestanasRamo
          inicial={pestana}
          pestanas={[
            {
              valor: "nuevo",
              etiqueta: "Lo nuevo",
              contenido:
                novedades.length === 0 ? (
                  <p className="text-sm text-texto-2">
                    No hay nada nuevo en los ultimos {DIAS_LO_NUEVO} dias.
                  </p>
                ) : (
                  <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                    {novedades.map((novedad) => (
                      <Novedad
                        key={`${novedad.tipo}-${novedad.id}`}
                        novedad={novedad}
                        nombreRamo={curso.name}
                        colorRamo={color}
                        ahora={ahora}
                      />
                    ))}
                  </ul>
                ),
            },
            {
              valor: "anuncios",
              etiqueta: "Anuncios",
              contenido:
                todosAnuncios.length === 0 ? (
                  <p className="text-sm text-texto-2">
                    Este ramo no tiene anuncios.
                  </p>
                ) : (
                  <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                    {todosAnuncios.map((anuncio) => (
                      <FilaAnuncio key={anuncio.canvas_id} anuncio={anuncio} />
                    ))}
                  </ul>
                ),
            },
            {
              valor: "tareas",
              etiqueta: "Tareas",
              contenido: (
                <div className="flex flex-col gap-5">
                  {(
                    [
                      ["Proximas", tareasOrdenadas.proximas],
                      ["Sin fecha", tareasOrdenadas.sinFecha],
                      ["Pasadas", tareasOrdenadas.pasadas],
                    ] as const
                  ).map(([titulo, lista]) =>
                    lista.length > 0 ? (
                      <section key={titulo} className="flex flex-col gap-2">
                        <h2 className="text-sm font-semibold text-texto">
                          {titulo}
                        </h2>
                        <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                          {lista.map((tarea) => (
                            <FilaTarea
                              key={tarea.canvas_id}
                              tarea={tarea}
                              ahora={ahora}
                            />
                          ))}
                        </ul>
                      </section>
                    ) : null,
                  )}
                  {tareasOrdenadas.proximas.length +
                    tareasOrdenadas.sinFecha.length +
                    tareasOrdenadas.pasadas.length ===
                  0 ? (
                    <p className="text-sm text-texto-2">
                      Este ramo no tiene tareas.
                    </p>
                  ) : null}
                </div>
              ),
            },
            {
              valor: "material",
              etiqueta: "Material",
              contenido:
                grupos.length === 0 ? (
                  <p className="text-sm text-texto-2">
                    Todavia no hay material sincronizado de este ramo.
                  </p>
                ) : (
                  <div className="columns-1 gap-3 lg:columns-2">
                    {grupos.map((grupo) => (
                      <details
                        key={`${grupo.source}-${grupo.etiqueta}`}
                        open
                        className="mb-3 break-inside-avoid rounded-xl border border-borde bg-superficie p-4"
                      >
                        <summary className="cursor-pointer text-sm font-semibold text-texto">
                          {grupo.etiqueta}
                        </summary>
                        <ul className="mt-2">
                          {grupo.archivos.map((archivo) => (
                            <FilaArchivo
                              key={archivo.canvas_id}
                              archivo={archivo}
                            />
                          ))}
                        </ul>
                      </details>
                    ))}
                  </div>
                ),
            },
            {
              valor: "modulos",
              etiqueta: "Modulos",
              contenido: (
                <ListaModulos
                  modulos={modulos}
                  items={items}
                  archivosPorId={archivosPorId}
                />
              ),
            },
          ]}
        />
      </main>
    </>
  );
}
