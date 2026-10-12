import { defineConfig } from "vite";

// base "./" so the built site works from any path (GitHub Pages project pages,
// Cloudflare Pages, or a local file server) without rewrites.
export default defineConfig({
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
