import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Better Canvas",
    short_name: "Better Canvas",
    description: "Resumen de tus ramos de Canvas, sin entrar a Canvas.",
    start_url: "/",
    display: "standalone",
    background_color: "#0b0f16",
    theme_color: "#0b0f16",
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
