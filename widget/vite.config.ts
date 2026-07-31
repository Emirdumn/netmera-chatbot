import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Iki ayri cikti var:
 *
 *  - varsayilan mod : `src/main.tsx` -> gelistirme/demo sayfasi (Playground)
 *  - `--mode embed` : `src/embed.tsx` -> dis sitelere gomulecek tek dosyalik
 *                     IIFE paketi (widget.js + widget.css)
 */
export default defineConfig(({ mode }) => {
  if (mode === "embed") {
    return {
      plugins: [react()],
      define: { "process.env.NODE_ENV": JSON.stringify("production") },
      build: {
        outDir: "dist-embed",
        emptyOutDir: true,
        cssCodeSplit: false,
        lib: {
          entry: "src/embed.tsx",
          name: "NetmeraWidgetBundle",
          formats: ["iife"],
          fileName: () => "widget.js",
        },
        rollupOptions: {
          output: {
            // CSS tek dosya olarak widget.css adiyla ciksin — embed.tsx
            // kendi src'sinden bu ismi turetip <link> ekliyor.
            assetFileNames: "widget.[ext]",
          },
        },
      },
    };
  }

  return {
    plugins: [react()],
    server: { port: 5174 },
  };
});
