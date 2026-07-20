import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import pluginChecker from 'vite-plugin-checker';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), pluginChecker({ typescript: true })],
  optimizeDeps: {
    esbuildOptions: {
      supported: {
        "top-level-await": true, // Needed for bson
      },
    },
  },
  esbuild: {
    supported: {
      "top-level-await": true, // Needed for bson
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 3000,
    watch: {
      ignored: [
        "**/vci-capture-main/**",
        "**/vci-automation-main/**",
      ],
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern',
        silenceDeprecations: ['mixed-decls', 'color-functions', 'global-builtin', 'import'],
      },
    }
  }
});
