import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { createRequire } from "node:module";

/* A versão exibida na interface vem do `package.json`, não de uma constante
   escrita à mão: já houve tela anunciando a versão errada porque alguém subiu
   o `package.json` e esqueceu do resto. Aqui só existe um lugar. */
const { version } = createRequire(import.meta.url)("./package.json");

export default defineConfig({
  define: {
    __VERSAO_DO_APP__: JSON.stringify(version),
  },
  plugins: [react(), tailwindcss()],
  base: "./",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: "dist",
  },
  server: {
    watch: {
      // O Vite observa a raiz do projeto, e a raiz aqui guarda coisas que não
      // são código da interface: o `.venv` sozinho tem ~200 pacotes e 1,5 GB.
      // Observá-lo custa caro no Windows e produz recarga espúria — durante o
      // preparo desta máquina o log registrou um `page reload` disparado por
      // um arquivo do torch. Nenhuma destas pastas afeta o que o Vite serve.
      ignored: [
        "**/.venv/**",
        "**/python-backend/**",
        "**/resources/**",
        "**/release/**",
        "**/dist-electron/**",
      ],
    },
  },
});
