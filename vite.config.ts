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

    /* Fonte nunca é embutida como `data:` URI, e isto é a CSP falando, não
       gosto pessoal.

       O padrão do Vite embute todo asset com menos de 4 KB, e dois subconjuntos
       de fonte caem abaixo disso (os cirílicos do Plus Jakarta Sans e do
       JetBrains Mono, ~1,7 e ~2,0 KB). A CSP da janela tem `font-src 'self'`,
       que **não** aceita `data:` — então o navegador bloqueia a fonte embutida
       e registra a violação. Os outros dezesseis subconjuntos, que viram
       arquivo, carregam normalmente.

       O estrago hoje é console sujo: os dois bloqueados cobrem só o cirílico,
       que não aparece em processo brasileiro. O que torna isso pior que
       cosmético é o que vem depois — quatro erros de CSP a cada abertura
       ensinam a ignorar erro de CSP, e basta uma atualização de fonte encolher
       um subconjunto LATINO abaixo de 4 KB para o texto cair na fonte do
       sistema, em silêncio, sem nada além dessa mesma linha que ninguém lê
       mais.

       Só apareceu no aplicativo INSTALADO: em desenvolvimento o Vite serve as
       fontes por URL, e o `data:` nem chega a existir. */
    assetsInlineLimit: (arquivo) => (arquivo.endsWith(".woff2") ? false : undefined),
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
