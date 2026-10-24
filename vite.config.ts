import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      // serve public/<dir>/index.html for /<dir>/ like Vercel does
      name: "public-dir-index",
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url && /^\/(host-a|host-b|samples)\/?(\?.*)?$/.test(req.url)) req.url = req.url.replace(/\/?(\?.*)?$/, "/index.html$1");
          next();
        });
      },
    },
  ],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8010" } },
});
