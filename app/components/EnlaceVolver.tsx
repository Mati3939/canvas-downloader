import Link from "next/link";

export function EnlaceVolver({ href, texto }: { href: string; texto: string }) {
  return (
    <Link
      href={href}
      className="text-sm text-zinc-500 underline-offset-2 hover:underline dark:text-zinc-400"
    >
      ← {texto}
    </Link>
  );
}
