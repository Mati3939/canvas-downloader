import Link from "next/link";

export function EnlaceVolver({ href, texto }: { href: string; texto: string }) {
  return (
    <Link
      href={href}
      className="text-sm text-texto-2 underline-offset-2 hover:underline"
    >
      ← {texto}
    </Link>
  );
}
