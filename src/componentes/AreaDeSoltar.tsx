import { useCallback, useEffect, useRef, useState } from "react";
import type { FileItem } from "../types";
import type { ArquivoNaFila, EstadoArquivo } from "../estado/tipos";
import { Botao, Icone, Selo, Tecla } from "../ui";

/**
 * Área de soltar e fila de arquivos.
 *
 * A fila mostra em que estágio cada arquivo está (na fila / lendo /
 * anonimizando / pronto / falhou) e a falha de um arquivo aparece **com o
 * motivo**, ali na linha dele.
 *
 * O que **não** pode mudar, porque é essencial: `getPathForFile` do preload. O
 * `File.path` não existe mais no Electron, e sem o caminho real um documento
 * binário nem poderia ser aberto pelo backend — além de o resultado ser salvo
 * no diretório errado.
 *
 * A área e a fila são dois cartões, não um. Enquanto eram um bloco só, a fila
 * herdava a moldura tracejada e parecia parte do convite a soltar arquivo, em
 * vez do inventário do que já foi solto.
 */

const MAX_ARQUIVOS = 10;

/** Texto puro: o próprio renderer lê e manda o conteúdo. */
const EXTENSOES_TEXTO = [".txt", ".md", ".rtf"];

/** Documentos que o backend abre pelo caminho, fazendo OCR quando digitalizados. */
const EXTENSOES_DOCUMENTO = [
  ".pdf", ".docx", ".xlsx", ".pptx",
  ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp",
];

const EXTENSOES_ACEITAS = [...EXTENSOES_TEXTO, ...EXTENSOES_DOCUMENTO];

const ROTULO_ESTADO: Record<EstadoArquivo, string> = {
  "na-fila": "na fila",
  lendo: "lendo",
  anonimizando: "anonimizando",
  pronto: "pronto",
  falhou: "falhou",
};

function tamanhoLegivel(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface AreaDeSoltarProps {
  fila: ArquivoNaFila[];
  aoMudarFila: (arquivos: FileItem[]) => void;
  /** Trava a área enquanto o lote roda. */
  bloqueada?: boolean;
}

export function AreaDeSoltar({
  fila,
  aoMudarFila,
  bloqueada = false,
}: AreaDeSoltarProps) {
  const refInput = useRef<HTMLInputElement>(null);
  const [arrastando, setArrastando] = useState(false);
  const [recusados, setRecusados] = useState<string[]>([]);
  const [noLimite, setNoLimite] = useState(false);

  const acrescentar = useCallback(
    async (lista: FileList) => {
      const novos: FileItem[] = [];
      const naoAceitos: string[] = [];

      for (const arquivo of Array.from(lista)) {
        const ext = arquivo.name
          .substring(arquivo.name.lastIndexOf("."))
          .toLowerCase();

        if (!EXTENSOES_ACEITAS.includes(ext)) {
          naoAceitos.push(arquivo.name);
          continue;
        }
        if (fila.length + novos.length >= MAX_ARQUIVOS) break;
        if (fila.some((f) => f.name === arquivo.name)) continue;

        const caminho =
          window.electronAPI?.getPathForFile?.(arquivo) || arquivo.name;
        const precisaExtracao = EXTENSOES_DOCUMENTO.includes(ext);

        if (precisaExtracao && !window.electronAPI?.getPathForFile) {
          // Fora do Electron não há caminho de disco para entregar ao backend.
          naoAceitos.push(arquivo.name);
          continue;
        }

        let conteudo = "";
        if (!precisaExtracao) {
          /* UTF-8 estrito primeiro; caindo, assume cp1252 — comum em RTF
             gerado no Windows, e decodificar errado corromperia acentuação
             justamente nos nomes próprios que precisam ser detectados. */
          const buffer = await arquivo.arrayBuffer();
          try {
            conteudo = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
          } catch {
            conteudo = new TextDecoder("windows-1252").decode(buffer);
          }
        }

        novos.push({
          name: arquivo.name,
          path: caminho,
          content: conteudo,
          size: arquivo.size,
          precisaExtracao,
        });
      }

      if (novos.length > 0) aoMudarFila([...fila, ...novos]);
      setRecusados(naoAceitos);

      if (fila.length + novos.length >= MAX_ARQUIVOS) {
        setNoLimite(true);
        setTimeout(() => setNoLimite(false), 3000);
      }
    },
    [fila, aoMudarFila]
  );

  const abrirDialogo = useCallback(async () => {
    /* No Electron, o diálogo nativo é o caminho bom: ele traz o caminho de
       disco de graça e oferece PDF e Office no filtro. O `<input>` só entra
       fora do Electron. */
    if (window.electronAPI?.selectFiles) {
      const escolhidos = await window.electronAPI.selectFiles();
      if (escolhidos.length === 0) return;

      /* O diálogo nativo devolve caminho, não um `File`. Para PDF e Office isso
         basta: o backend abre pelo caminho. Para texto puro, **não** — a rota
         `/processar` recusa `.txt`, `.md` e `.rtf` por caminho (415), porque
         ler arquivo arbitrário do disco é justamente o que ela evita.

         Marcar tudo como `precisaExtracao` fazia o `.txt` escolhido pelo botão
         falhar sempre, enquanto o MESMO arquivo arrastado funcionava — o
         diálogo até oferece o filtro "Texto". O conserto é o renderer ler o
         conteúdo pelo IPC, exatamente como faz com um arquivo arrastado. */
      const lidos = await Promise.all(
        escolhidos
          .filter((e) => !fila.some((f) => f.name === e.name))
          .slice(0, MAX_ARQUIVOS - fila.length)
          .map(async (e) => {
            const ehTexto = EXTENSOES_TEXTO.some((ext) =>
              e.name.toLowerCase().endsWith(ext)
            );
            if (!ehTexto) {
              return {
                name: e.name,
                path: e.path,
                content: "",
                size: 0,
                precisaExtracao: true,
              };
            }
            try {
              const content = await window.electronAPI!.readFile(e.path);
              return {
                name: e.name,
                path: e.path,
                content,
                size: content.length,
                precisaExtracao: false,
              };
            } catch {
              /* Ilegível como texto: deixa o backend tentar, que sabe dizer o
                 motivo na linha do arquivo em vez de sumir com ele. */
              return {
                name: e.name,
                path: e.path,
                content: "",
                size: 0,
                precisaExtracao: true,
              };
            }
          })
      );
      const novos: FileItem[] = lidos;

      if (novos.length > 0) aoMudarFila([...fila, ...novos]);
      return;
    }
    refInput.current?.click();
  }, [fila, aoMudarFila]);

  /* Ctrl+O abre o mesmo diálogo. O atalho vive num `ref` para o ouvinte ser
     registrado uma vez só: com `abrirDialogo` na lista de dependências, cada
     arquivo acrescentado remontaria o ouvinte. */
  const refAbrir = useRef(abrirDialogo);
  refAbrir.current = abrirDialogo;
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
      if (e.key.toLowerCase() !== "o") return;
      e.preventDefault();
      void refAbrir.current();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, []);

  return (
    <div className="flex flex-col gap-gutter-md">
      <div
        onDrop={(e) => {
          e.preventDefault();
          setArrastando(false);
          if (!bloqueada && e.dataTransfer.files.length > 0) {
            acrescentar(e.dataTransfer.files);
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!bloqueada) setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        className={[
          "group relative flex min-h-[340px] flex-col items-center justify-center overflow-hidden",
          "rounded-xl bg-surface-container-lowest p-gutter-2xl text-center shadow-sm",
          "transition-all duration-300 hover:shadow-md",
          arrastando ? "scale-[1.01] bg-surface-container-high/40" : "",
          bloqueada ? "pointer-events-none opacity-50" : "",
        ].join(" ")}
      >
        {/* Dois halos desfocados nos cantos opostos. É o único ornamento do
            sistema, e existe porque esta é a única tela que fica vazia
            esperando uma ação — sem ele o retângulo branco não convida a
            nada. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full bg-primary-fixed/25 blur-3xl transition-transform duration-500 group-hover:scale-110"
        />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-24 -left-24 h-64 w-64 rounded-full bg-secondary-fixed/20 blur-3xl transition-transform duration-500 group-hover:scale-110"
        />

        {/* A moldura tracejada é desenhada com gradientes repetidos em vez de
            `border-dashed`: assim o traço tem passo constante nos quatro lados
            e a cor do traço pode acender no arrasto sem mexer no raio. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-4 rounded-lg opacity-80 transition-opacity group-hover:opacity-100"
          style={{
            backgroundImage: [0, 90, 180, 270]
              .map(
                (g) =>
                  `repeating-linear-gradient(${g}deg,var(--traco),var(--traco) 8px,transparent 8px,transparent 16px)`
              )
              .join(","),
            backgroundSize: "2px 100%, 100% 2px, 2px 100%, 100% 2px",
            backgroundPosition: "0 0, 0 0, 100% 0, 0 100%",
            backgroundRepeat: "no-repeat",
            ["--traco" as string]: arrastando
              ? "var(--primary)"
              : "var(--outline-variant)",
          }}
        />

        <div className="relative z-10 flex max-w-md flex-col items-center gap-gutter-md">
          <span
            className={[
              "grid size-16 place-items-center rounded-xl shadow-sm transition-all duration-300",
              arrastando
                ? "scale-105 bg-primary-container text-on-primary"
                : "bg-surface-container text-primary group-hover:scale-105 group-hover:bg-primary-container group-hover:text-on-primary",
            ].join(" ")}
          >
            <Icone nome="drive_folder_upload" tamanho={34} />
          </span>

          <div className="flex flex-col gap-gutter-xs">
            <h3 className="font-display text-headline-lg text-on-surface">
              Arraste os autos direto do PJe
            </h3>
            <p className="font-body text-body-md text-on-surface-variant">
              Serve para a exportação integral do processo ou para peças avulsas
              escaneadas.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-1.5 pt-1">
            {["PDF (texto ou OCR)", "DOCX", "XLSX", "TXT", "imagem"].map((f) => (
              <span
                key={f}
                className="rounded-xs bg-surface-container-low px-2 py-0.5 font-mono text-mono-tag text-on-surface-variant"
              >
                {f}
              </span>
            ))}
            <span className="rounded-xs bg-surface-container-high px-2 py-0.5 font-mono text-mono-tag text-primary">
              até {MAX_ARQUIVOS} por lote
            </span>
          </div>

          <div className="mt-2 flex items-center gap-gutter-sm">
            <Botao
              tipo="primario"
              tamanho="grande"
              icone="file_open"
              onClick={abrirDialogo}
              disabled={bloqueada}
            >
              Escolher arquivos do computador
            </Botao>
            <span className="hidden items-center gap-1.5 sm:flex">
              <span className="font-body text-body-sm text-outline">ou</span>
              <Tecla>Ctrl+O</Tecla>
            </span>
          </div>
        </div>
      </div>

      <input
        ref={refInput}
        type="file"
        multiple
        accept={EXTENSOES_ACEITAS.join(",")}
        className="hidden"
        onChange={(e) => {
          if (e.target.files) acrescentar(e.target.files);
          e.target.value = "";
        }}
      />

      {noLimite && (
        <p role="status" className="font-body text-body-sm text-on-tertiary-container">
          Limite de {MAX_ARQUIVOS} arquivos por lote atingido.
        </p>
      )}

      {recusados.length > 0 && (
        <p role="status" className="font-body text-body-sm text-on-tertiary-container">
          Não dá para ler {recusados.join(", ")}. São aceitos PDF, DOCX, XLSX,
          PPTX, imagens digitalizadas, TXT, MD e RTF.
        </p>
      )}

      {fila.length > 0 && (
        <div className="flex flex-col gap-gutter-sm rounded-lg bg-surface-container-lowest p-gutter-md shadow-sm">
          <div className="flex items-center justify-between gap-gutter-sm">
            <div className="flex items-center gap-gutter-xs">
              <h3 className="font-display text-headline-sm text-on-surface">Lote em fila</h3>
              <Selo tom="acao" forma="pilula">
                {`${fila.length} peça${fila.length > 1 ? "s" : ""}`}
              </Selo>
            </div>
            {!bloqueada && (
              <Botao
                tipo="perigo"
                tamanho="mini"
                icone="delete_sweep"
                onClick={() => aoMudarFila([])}
              >
                Limpar lote
              </Botao>
            )}
          </div>

          <ul className="flex flex-col gap-gutter-xs">
            {fila.map((arquivo, i) => (
              <li
                key={arquivo.path || arquivo.name}
                className="flex items-center justify-between gap-gutter-sm rounded-sm bg-surface-container-low/80 p-gutter-sm transition-colors duration-[120ms] hover:bg-surface-container-low"
              >
                <div className="flex min-w-0 items-center gap-gutter-sm">
                  <span className="grid size-9 shrink-0 place-items-center rounded-xs bg-surface-container text-primary">
                    <Icone
                      nome={arquivo.precisaExtracao ? "picture_as_pdf" : "description"}
                      tamanho={20}
                    />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-mono text-mono-code text-on-surface">
                      {arquivo.name}
                    </p>
                    {arquivo.estado === "falhou" && arquivo.motivoDaFalha ? (
                      /* O motivo fica na linha do arquivo, não num toast que
                         some: com um lote de dez, saber *qual* falhou e *por
                         quê* é a informação inteira. */
                      <p className="mt-0.5 font-body text-body-sm text-error">
                        {arquivo.motivoDaFalha}
                      </p>
                    ) : (
                      <p className="mt-0.5 font-mono text-mono-tag text-on-surface-variant">
                        {arquivo.size > 0
                          ? tamanhoLegivel(arquivo.size)
                          : "tamanho lido pelo motor"}
                        {arquivo.precisaExtracao && " · passa por reconhecimento de texto"}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-gutter-sm">
                  <Selo
                    tom={
                      arquivo.estado === "falhou"
                        ? "perigo"
                        : arquivo.estado === "pronto"
                          ? "deferido"
                          : arquivo.estado === "na-fila"
                            ? "neutro"
                            : "acao"
                    }
                    comPonto={arquivo.estado !== "na-fila"}
                  >
                    {ROTULO_ESTADO[arquivo.estado]}
                  </Selo>

                  {!bloqueada && (
                    <button
                      type="button"
                      onClick={() => aoMudarFila(fila.filter((_, n) => n !== i))}
                      aria-label={`Remover ${arquivo.name}`}
                      className="rounded-xs p-1 text-outline transition-colors duration-[120ms] hover:text-error"
                    >
                      <Icone nome="close" tamanho={16} />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
