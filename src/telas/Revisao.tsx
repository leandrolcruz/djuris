import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useApp } from "../estado/AppEstado";
import { corDaEntidade, rotuloDaEntidade } from "../types";
import type { EntityFound, ProcessedFile } from "../types";
import { agruparPorTipo, segmentar } from "../lib/segmentar";
import { nomeDeSaida } from "../lib/nomeDeSaida";
import { Botao, Dialogo, GrupoSegmentado, Icone, Popover, Selo, Tarja } from "../ui";

/**
 * Revisão — conferir as tarjas antes de assinar embaixo.
 *
 * Não é destino do trilho: abre sobre o destino atual, ao terminar um
 * processamento ou ao escolher um documento no cofre.
 *
 * ## Duas formas de tirar uma tarja, e elas não são a mesma coisa
 *
 * Até aqui existia uma só: "liberar" gravava o termo na deny-list e ele deixava
 * de ser mascarado **em todos os documentos, para sempre**. Isso é a resposta
 * certa para "nome de vara" e a errada para "este parágrafo específico não é
 * dado de ninguém" — e, sem alternativa, o revisor usava a permanente para
 * resolver o caso pontual.
 *
 * Agora são duas:
 *
 * - **O olho** libera a ocorrência **neste documento**. Reversível, coberta
 *   pelo desfazer, não toca política nenhuma.
 * - **"Não é dado pessoal"** grava na lista de termos liberados. Continua
 *   pedindo confirmação, porque continua valendo para sempre.
 *
 * ## Desfazer é sobre as máscaras deste documento
 *
 * A pilha guarda os conjuntos de ocorrências pelos quais o documento passou.
 * Ela **é do documento aberto**: paginar para outro arquivo do lote começa uma
 * pilha nova, porque desfazer no arquivo 3 uma ação feita no arquivo 1 seria
 * pior que não desfazer.
 *
 * O que a pilha **não** desfaz é a gravação na deny-list — essa se reverte nos
 * Ajustes, onde os termos liberados são listados. O diálogo de confirmação diz
 * isso com todas as letras.
 *
 * ## O painel de ocorrências não some
 *
 * Era `hidden … lg:block`, então evaporava abaixo de 1024px — e com ele a
 * auditoria inteira, que é a tarefa central de quem responde pelo sigilo. Numa
 * janela estreita não havia como conferir nada. Vira gaveta.
 *
 * ## As tarjas entram varrendo
 *
 * 240 ms no total, escalonadas pela ordem da ocorrência: o documento sendo
 * carimbado. É o único momento orquestrado do sistema. Quem pediu menos
 * movimento no sistema operacional não recebe nenhum, pelo bloco
 * `prefers-reduced-motion` do `tokens.css`.
 */

type Modo = "revisar" | "resultado";

interface RevisaoProps {
  aoSalvarTodos: () => void;
  aoBaixarArquivo: (arquivo: ProcessedFile) => void;
  /* Recebe o índice porque a rejeição reescreve ESTE documento; sem ele o
     App teria de adivinhar qual dos arquivos do lote está aberto. */
  aoRejeitarDeteccao: (entidade: EntityFound, indiceArquivo: number) => void;
  /** Reescreve a saída com este conjunto de ocorrências. Devolve o resultado. */
  aoAplicarMascaras: (
    indiceArquivo: number,
    entidades: EntityFound[]
  ) => Promise<ProcessedFile | null>;
}

export function Revisao({
  aoSalvarTodos,
  aoBaixarArquivo,
  aoRejeitarDeteccao,
  aoAplicarMascaras,
}: RevisaoProps) {
  const { estado, despachar, prefs, definirPref } = useApp();
  const revisao = estado.revisao;

  const [indiceArquivo, setIndiceArquivo] = useState(0);
  const [modo, setModo] = useState<Modo>("revisar");
  const [ocorrenciaAtiva, setOcorrenciaAtiva] = useState<number | null>(null);
  /* Recolher um tipo é o que os chips de filtro faziam, sem a faixa de chips:
     o agrupamento já mostra os tipos e a contagem, e recolher é o filtro. */
  const [recolhidos, setRecolhidos] = useState<Set<string>>(new Set());
  /* Ordem do documento é o padrão porque se revisa de cima para baixo. A
     alternativa serve à pergunta que o revisor faz quando o lote é grande:
     "o que tem mais chance de estar errado?" — e ela só passou a ter resposta
     honesta quando o score deixou de ser o máximo do tipo no documento inteiro
     e passou a ser o da ocorrência. */
  const [fracasPrimeiro, setFracasPrimeiro] = useState(false);
  const [gavetaAberta, setGavetaAberta] = useState(false);
  const [aRejeitar, setARejeitar] = useState<EntityFound | null>(null);
  const [liberarTudo, setLiberarTudo] = useState(false);
  const [salvarSemMascara, setSalvarSemMascara] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const areaTexto = useRef<HTMLDivElement>(null);

  const arquivos = revisao?.arquivos ?? [];
  const indiceSeguro = Math.min(indiceArquivo, Math.max(0, arquivos.length - 1));
  const arquivo = arquivos[indiceSeguro];

  /* Pilha de desfazer, do documento aberto. `pilha[pos]` é o estado atual.

     A dependência é o **caminho** do arquivo, e isso é load-bearing: cada
     máscara aplicada despacha `substituir-em-revisao`, que devolve um
     `estado.revisao` novo. Dependendo do objeto, o efeito rodaria depois de
     toda ação, zeraria a pilha, e o desfazer nunca ficaria disponível — sem
     erro nenhum, só um botão permanentemente apagado. */
  const caminhoAberto = arquivos[indiceSeguro]?.originalPath;
  const [pilha, setPilha] = useState<EntityFound[][]>([]);
  const [pos, setPos] = useState(0);
  useEffect(() => {
    setPilha(arquivos[indiceSeguro] ? [arquivos[indiceSeguro].entitiesFound] : []);
    setPos(0);
    setOcorrenciaAtiva(null);
    // Só ao trocar de documento aberto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indiceSeguro, caminhoAberto]);

  /* A varredura roda uma vez, ao abrir vindo do processamento. Abrir do cofre
     não anima: o documento não está sendo carimbado agora, já foi. */
  const [varrendo, setVarrendo] = useState(revisao?.origem === "processamento");
  useEffect(() => {
    if (!varrendo) return;
    const t = setTimeout(() => setVarrendo(false), 700);
    return () => clearTimeout(t);
  }, [varrendo]);

  const grupos = useMemo(
    () => agruparPorTipo(arquivo?.entitiesFound ?? [], fracasPrimeiro),
    [arquivo, fracasPrimeiro]
  );

  const segmentos = useMemo(
    () => segmentar(arquivo?.originalContent ?? "", arquivo?.entitiesFound ?? []),
    [arquivo]
  );

  const irParaOcorrencia = useCallback((indice: number) => {
    setOcorrenciaAtiva(indice);
    const alvo = areaTexto.current?.querySelector(`[data-ocorrencia="${indice}"]`);
    alvo?.scrollIntoView({ block: "center", behavior: "smooth" });
    (alvo as HTMLElement | null)?.focus();
  }, []);

  /** Aplica um conjunto novo e empilha. */
  const aplicarEEmpilhar = useCallback(
    async (entidades: EntityFound[]) => {
      setOcupado(true);
      try {
        const feito = await aoAplicarMascaras(indiceSeguro, entidades);
        if (!feito) return;
        setPilha((p) => [...p.slice(0, pos + 1), feito.entitiesFound]);
        setPos((n) => n + 1);
      } finally {
        setOcupado(false);
      }
    },
    [aoAplicarMascaras, indiceSeguro, pos]
  );

  /** Anda na pilha sem empilhar de novo — é isto que desfazer e refazer fazem. */
  const irNaPilha = useCallback(
    async (destino: number) => {
      if (destino < 0 || destino >= pilha.length) return;
      setOcupado(true);
      try {
        const feito = await aoAplicarMascaras(indiceSeguro, pilha[destino]);
        if (feito) setPos(destino);
      } finally {
        setOcupado(false);
      }
    },
    [aoAplicarMascaras, indiceSeguro, pilha]
  );

  const podeDesfazer = pos > 0 && !ocupado;
  const podeRefazer = pos < pilha.length - 1 && !ocupado;

  /* Ctrl+Z / Ctrl+Y, os atalhos que o desenho promete nos títulos dos botões. */
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "z" && !e.shiftKey && podeDesfazer) {
        e.preventDefault();
        void irNaPilha(pos - 1);
      } else if ((k === "y" || (k === "z" && e.shiftKey)) && podeRefazer) {
        e.preventDefault();
        void irNaPilha(pos + 1);
      }
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [podeDesfazer, podeRefazer, irNaPilha, pos]);

  if (!revisao || !arquivo) return null;

  const total = arquivo.entitiesFound.length;
  const saida = nomeDeSaida(arquivo.originalName, prefs.formato);
  const ocr = arquivo.ocr;
  const semMascara = total === 0;

  /** Tira uma ocorrência da lista deste documento — sem tocar em política. */
  const liberarUma = (indice: number) =>
    aplicarEEmpilhar(arquivo.entitiesFound.filter((_, n) => n !== indice));

  /**
   * O painel de auditoria, usado tanto na coluna fixa quanto na gaveta.
   *
   * O agrupamento por tipo substituiu a faixa de chips coloridos que ficava sob
   * a barra de ações: ela repetia a informação que os cabeçalhos de grupo já
   * dão (quais tipos existem e quantos), numa faixa de cor forte que competia
   * com o documento — e o documento é o que se veio ler.
   */
  const painelOcorrencias = (
    <div className="flex flex-col gap-gutter-md rounded-lg bg-surface-container-lowest p-gutter-lg shadow-md">
      <div className="flex items-center justify-between gap-gutter-sm">
        <h2 className="flex items-center gap-gutter-xs font-display text-headline-lg text-on-surface">
          {total} {total === 1 ? "ocorrência" : "ocorrências"}
          <span
            aria-hidden="true"
            className={`inline-block size-2 rounded-full ${semMascara ? "bg-error" : "bg-secondary"}`}
          />
        </h2>
        {total > 1 && (
          <button
            type="button"
            aria-pressed={fracasPrimeiro}
            onClick={() => setFracasPrimeiro((v) => !v)}
            title={
              fracasPrimeiro
                ? "Ordenado pela confiança, do mais duvidoso ao mais certo"
                : "Ordenado pela posição no documento"
            }
            className="flex items-center gap-1 rounded-sm bg-surface-container-low px-2 py-1 font-mono text-mono-tag text-on-surface-variant transition-colors duration-[120ms] hover:text-on-surface"
          >
            {fracasPrimeiro ? "menos certas" : "ordem do texto"}
            <Icone nome="unfold_more" tamanho={14} />
          </button>
        )}
      </div>

      <p className="font-body text-body-sm text-on-surface-variant">
        Confira cada item. O olho tira a tarja <strong>só deste documento</strong>; "não é dado
        pessoal" tira o termo de todos os documentos seguintes.
      </p>

      <div className="flex flex-col gap-gutter-sm">
        {grupos.map(({ tipo, itens }) => {
          const recolhido = recolhidos.has(tipo);
          const cor = corDaEntidade(tipo);
          return (
            <section key={tipo} className="overflow-hidden rounded-lg bg-surface-container-low/60">
              <h3>
                <button
                  type="button"
                  onClick={() =>
                    setRecolhidos((atual) => {
                      const proximo = new Set(atual);
                      if (proximo.has(tipo)) proximo.delete(tipo);
                      else proximo.add(tipo);
                      return proximo;
                    })
                  }
                  aria-expanded={!recolhido}
                  className="flex w-full items-center gap-2 bg-surface-container-low p-gutter-sm text-left transition-colors duration-[120ms] hover:bg-surface-container"
                >
                  <span
                    aria-hidden="true"
                    className="size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: cor }}
                  />
                  <span className="min-w-0 flex-1 truncate font-display text-body-md text-on-surface">
                    {rotuloDaEntidade(tipo)}
                  </span>
                  <span className="font-mono text-mono-code text-on-surface-variant tabular-nums">
                    {itens.length}
                  </span>
                  <Icone
                    nome={recolhido ? "expand_more" : "expand_less"}
                    tamanho={16}
                    className="shrink-0 text-outline"
                  />
                </button>
              </h3>

              {!recolhido && (
                <ul>
                  {itens.map(({ entidade, indice }) => (
                    <li
                      key={indice}
                      className={`flex items-center gap-2 px-gutter-sm py-2 transition-colors duration-[120ms] ${
                        ocorrenciaAtiva === indice ? "bg-surface-container" : ""
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => irParaOcorrencia(indice)}
                        className="min-w-0 flex-1 rounded-sm text-left"
                      >
                        <span className="block truncate font-mono text-mono-code text-on-surface">
                          {entidade.text}
                        </span>
                        <span className="block font-mono text-mono-tag text-on-surface-variant">
                          {Math.round(entidade.score * 100)}% de confiança
                        </span>
                      </button>

                      <span className="flex shrink-0 items-center gap-0.5">
                        <button
                          type="button"
                          disabled={ocupado}
                          onClick={() => void liberarUma(indice)}
                          title="Tirar a tarja só neste documento (Ctrl+Z desfaz)"
                          aria-label={`Tirar a tarja de "${entidade.text}" neste documento`}
                          className="grid size-7 place-items-center rounded-sm bg-secondary-container/60 text-on-secondary-container transition-colors duration-[120ms] hover:bg-secondary-container disabled:opacity-40"
                        >
                          <Icone nome="visibility_off" tamanho={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setARejeitar(entidade)}
                          title="Não é dado pessoal — nunca mascarar este termo"
                          aria-label={`Marcar "${entidade.text}" como não sendo dado pessoal`}
                          className="grid size-7 place-items-center rounded-sm text-outline transition-colors duration-[120ms] hover:bg-surface-container-high hover:text-on-surface"
                        >
                          <Icone nome="person_off" tamanho={16} />
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>

      {total === 0 && (
        <p className="rounded-lg bg-error-container/40 p-gutter-md text-center font-body text-body-sm text-on-error-container">
          Nenhuma tarja neste documento. O texto salvo será igual ao original.
        </p>
      )}
    </div>
  );

  return (
    <div className="flex h-full animate-fade-in flex-col overflow-hidden">
      {/*
        Barra de ações — uma linha, três zonas: onde estou (esquerda), o que
        estou vendo (centro), o que faço com isso (direita).

        As abas por arquivo saíram: nomes do PJe têm prefixo numérico e sufixo
        de id ("036_Decisao_221675339.txt"), então todas começam e terminam
        iguais e o meio é o que distingue — exatamente o que a truncagem come.
        Um paginador mostra o nome inteiro de um documento por vez e não cresce
        com o tamanho do lote.
      */}
      <div className="z-30 flex shrink-0 flex-wrap items-center justify-between gap-gutter-md bg-surface-container-lowest px-gutter-xl py-gutter-sm shadow-sm">
        <div className="flex min-w-0 items-center gap-gutter-md">
          <Botao
            icone="arrow_back"
            onClick={() => despachar({ tipo: "fechar-revisao" })}
          >
            Voltar
          </Botao>

          <span aria-hidden="true" className="h-5 w-px bg-surface-container-highest" />

          <div className="flex min-w-0 items-center gap-2">
            <span className="shrink-0 text-primary">
              <Icone nome="description" tamanho={20} />
            </span>
            <span className="min-w-0 truncate font-display text-headline-sm text-on-surface">
              {arquivo.originalName}
            </span>
            <Selo tom={semMascara ? "perigo" : "deferido"} forma="pilula">
              {semMascara ? "SEM TARJA" : "SIGILOSO"}
            </Selo>
          </div>

          {arquivos.length > 1 && (
            <div className="flex shrink-0 items-center gap-1">
              <Botao
                tamanho="mini"
                tipo="discreto"
                circular
                icone="chevron_left"
                disabled={indiceSeguro === 0}
                onClick={() => setIndiceArquivo(indiceSeguro - 1)}
                aria-label="Documento anterior"
              />
              <span aria-live="polite" className="font-mono text-mono-tag text-outline tabular-nums">
                {indiceSeguro + 1} de {arquivos.length}
              </span>
              <Botao
                tamanho="mini"
                tipo="discreto"
                circular
                icone="chevron_right"
                disabled={indiceSeguro === arquivos.length - 1}
                onClick={() => setIndiceArquivo(indiceSeguro + 1)}
                aria-label="Próximo documento"
              />
            </div>
          )}
        </div>

        <GrupoSegmentado
          rotulo="Modo de visualização"
          opcoes={[
            {
              valor: "revisar" as const,
              rotulo: "Revisar (tarjas)",
              icone: "visibility_off" as const,
              descricao: "Texto original com as tarjas",
            },
            {
              valor: "resultado" as const,
              rotulo: "Resultado final",
              icone: "article" as const,
              descricao: "O texto que vai ser salvo",
            },
          ]}
          valor={modo}
          onChange={setModo}
        />

        <div className="flex shrink-0 items-center gap-gutter-xs">
          <div className="mr-1 flex items-center gap-0.5 rounded-sm bg-surface-container-low p-0.5">
            <Botao
              tamanho="mini"
              tipo="discreto"
              circular
              icone="undo"
              disabled={!podeDesfazer}
              onClick={() => void irNaPilha(pos - 1)}
              title="Desfazer (Ctrl+Z)"
              aria-label="Desfazer"
            />
            <Botao
              tamanho="mini"
              tipo="discreto"
              circular
              icone="redo"
              disabled={!podeRefazer}
              onClick={() => void irNaPilha(pos + 1)}
              title="Refazer (Ctrl+Y)"
              aria-label="Refazer"
            />
          </div>

          <Botao
            icone="visibility"
            disabled={semMascara || ocupado}
            onClick={() => setLiberarTudo(true)}
            title="Tirar todas as tarjas deste documento"
          >
            Liberar todas
          </Botao>

          <Botao
            tipo="primario"
            icone="lock_reset"
            disabled={semMascara}
            title={
              semMascara
                ? "Não há tarja nenhuma: o texto salvo seria igual ao original."
                : undefined
            }
            onClick={aoSalvarTodos}
          >
            Salvar e validar
            {arquivos.length > 1 ? ` · ${arquivos.length}` : ""}
          </Botao>

          {semMascara && (
            /* Salvar sem tarja nenhuma é gravar o documento em claro. Não pode
               ser o mesmo clique da entrega normal, mas também não pode ser
               impossível: pode ser um documento em que o motor não achou nada e
               o revisor conferiu. Botão separado, com confirmação própria. */
            <Botao tipo="perigo" onClick={() => setSalvarSemMascara(true)}>
              Salvar em claro
            </Botao>
          )}

          <Popover
            rotulo="Mais ações"
            alinhamento="fim"
            larguraMinima={280}
            gatilho={(props) => (
              <Botao {...props} tipo="discreto" circular icone="more_vert" aria-label="Mais ações" />
            )}
          >
            <div className="flex flex-col gap-gutter-md">
              <div>
                <p className="mb-1.5 font-mono text-mono-tag tracking-wider text-outline uppercase">
                  Formato do arquivo salvo
                </p>
                {/* A saída é texto — nunca o formato de entrada. Gravar markdown
                    dentro de um `.pdf` produzia um arquivo que nenhum leitor
                    abre. */}
                <GrupoSegmentado
                  rotulo="Formato de saída"
                  opcoes={[
                    { valor: "md" as const, rotulo: "MD", descricao: "Markdown — abre em qualquer editor" },
                    { valor: "docx" as const, rotulo: "DOCX", descricao: "Word, LibreOffice ou Google Docs" },
                  ]}
                  valor={prefs.formato}
                  onChange={(f) => definirPref("formato", f)}
                />
                <p className="mt-1.5 truncate font-mono text-mono-tag text-outline">{saida}</p>
              </div>
              <Botao icone="file_download" onClick={() => aoBaixarArquivo(arquivo)}>
                Baixar cópia deste
              </Botao>
            </div>
          </Popover>

          {/* Abaixo de 1280px o painel vira gaveta; o botão só existe aí. */}
          <Botao
            className="xl:hidden"
            icone="checklist"
            onClick={() => setGavetaAberta(true)}
            aria-label="Abrir a lista de ocorrências"
          >
            {total}
          </Botao>
        </div>
      </div>

      {/* Como o documento foi lido. `paginas_com_erro` não pode ser escondido:
          são páginas que precisavam de OCR e não voltaram. O texto delas não
          está no resultado, e quem revisa precisa saber antes de assinar. */}
      {ocr?.houve_ocr && (
        <div
          role={ocr.paginas_com_erro > 0 ? "alert" : "status"}
          className={`flex shrink-0 items-start gap-2 px-gutter-xl py-gutter-sm font-body text-body-sm ${
            ocr.paginas_com_erro > 0
              ? "bg-error-container/50 text-on-error-container"
              : "bg-tertiary-fixed/60 text-on-tertiary-fixed-variant"
          }`}
        >
          <Icone nome="warning" tamanho={16} className="mt-0.5 shrink-0" />
          <div className="min-w-0">
            {ocr.paginas_com_erro > 0 ? (
              <>
                <strong>
                  {ocr.paginas_com_erro}{" "}
                  {ocr.paginas_com_erro === 1 ? "página não foi lida" : "páginas não foram lidas"}
                </strong>
                {" — o texto delas não está aqui, e o que não está aqui não foi anonimizado nem revisado."}
              </>
            ) : (
              <>
                <strong>
                  {ocr.paginas_ocr} de {ocr.total_paginas}{" "}
                  {ocr.total_paginas === 1 ? "página lida" : "páginas lidas"} por reconhecimento de
                  imagem
                </strong>
                {" — reconhecimento erra; confira o resultado antes de entregar."}
              </>
            )}
          </div>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 items-start gap-gutter-lg overflow-y-auto px-gutter-xl py-gutter-lg xl:grid-cols-[minmax(0,1fr)_360px]">
        {/* Texto do documento */}
        <div ref={areaTexto} className="flex min-w-0 flex-col gap-gutter-md">
          <div className="flex items-center justify-between gap-gutter-md rounded-lg bg-surface-container-low px-gutter-md py-gutter-xs">
            <span className="flex min-w-0 items-center gap-2">
              <span className="text-outline">
                <Icone nome="terminal" tamanho={16} />
              </span>
              <span className="truncate font-mono text-mono-tag text-outline">→ {saida}</span>
            </span>
            {modo === "revisar" && (
              <p className="hidden font-body text-body-sm text-on-surface-variant md:block">
                Cada tarja esconde um dado detectado. Passe o cursor — ou navegue por teclado —
                para conferir o valor por baixo.
              </p>
            )}
          </div>

          <div className="relative rounded-lg bg-surface-container-lowest p-gutter-2xl shadow-md">
            {/* O selo do canto diz como o documento foi mascarado. A referência
                de desenho põe aqui um MD5 do arquivo; o produto não calcula
                nenhum, e inventar um hash seria a pior espécie de enfeite —
                aquele que parece prova. */}
            <div className="absolute top-gutter-md right-gutter-lg flex items-center gap-2 rounded-xs bg-surface-container px-2.5 py-1 font-mono text-mono-tag text-primary">
              <Icone nome="verified" tamanho={14} />
              <span>
                {total} {total === 1 ? "tarja" : "tarjas"} ·{" "}
                {modo === "revisar" ? "conferindo o original" : "saída anonimizada"}
              </span>
            </div>

            <article className="texto-documento mx-auto whitespace-pre-wrap text-on-surface">
              {modo === "resultado"
                ? arquivo.anonymizedContent
                : segmentos.map((seg, i) =>
                    seg.tipo === "texto" ? (
                      <span key={i}>{seg.conteudo}</span>
                    ) : (
                      <Tarja
                        key={i}
                        tipo={seg.entidade.type}
                        indice={seg.indice}
                        score={seg.entidade.score}
                        ativa={ocorrenciaAtiva === seg.indice}
                        revelada={ocorrenciaAtiva === seg.indice}
                        varrendo={varrendo}
                        onClick={() =>
                          setOcorrenciaAtiva(ocorrenciaAtiva === seg.indice ? null : seg.indice)
                        }
                        aoLiberar={() => void liberarUma(seg.indice)}
                      >
                        {seg.conteudo}
                      </Tarja>
                    )
                  )}
            </article>
          </div>
        </div>

        {/* Painel de ocorrências: coluna fixa a partir de 1280px. */}
        <aside
          aria-label="Ocorrências detectadas"
          className="sticky top-0 hidden xl:block"
        >
          {painelOcorrencias}
        </aside>
      </div>

      {/* …e gaveta abaixo disso, para a auditoria nunca ficar inalcançável. */}
      {gavetaAberta && (
        <div
          className="fixed inset-0 z-100 flex justify-end bg-[var(--veu)] xl:hidden"
          onClick={(e) => {
            if (e.target === e.currentTarget) setGavetaAberta(false);
          }}
        >
          <div
            role="dialog"
            aria-label="Ocorrências detectadas"
            className="flex w-[min(24rem,92vw)] flex-col overflow-y-auto bg-surface-container-low p-gutter-sm"
          >
            <div className="flex justify-end">
              <Botao
                tamanho="mini"
                tipo="discreto"
                circular
                icone="close"
                onClick={() => setGavetaAberta(false)}
                aria-label="Fechar a lista de ocorrências"
              />
            </div>
            {painelOcorrencias}
          </div>
        </div>
      )}

      <Dialogo
        aberto={aRejeitar !== null}
        aoFechar={() => setARejeitar(null)}
        titulo="Nunca mais mascarar este termo"
        acoes={
          <>
            <Botao tipo="secundario" onClick={() => setARejeitar(null)}>
              Cancelar
            </Botao>
            <Botao
              tipo="perigo"
              onClick={() => {
                if (aRejeitar) aoRejeitarDeteccao(aRejeitar, indiceSeguro);
                setARejeitar(null);
              }}
            >
              Liberar o termo
            </Botao>
          </>
        }
      >
        <p>
          <strong className="text-on-surface">“{aRejeitar?.text}”</strong> deixa de ser mascarado —
          neste e em <strong className="text-on-surface">todos</strong> os documentos seguintes,
          até você removê-lo nos Ajustes.
        </p>
        <p className="mt-2">
          Use quando for mesmo um falso positivo geral: um nome de vara, um termo técnico, um nome
          de instituição. Para tirar a tarja <strong>só aqui</strong>, use o olho na lista — essa
          o desfazer reverte, esta não.
        </p>
      </Dialogo>

      <Dialogo
        aberto={liberarTudo}
        aoFechar={() => setLiberarTudo(false)}
        titulo="Tirar todas as tarjas deste documento"
        acoes={
          <>
            <Botao tipo="secundario" onClick={() => setLiberarTudo(false)}>
              Cancelar
            </Botao>
            <Botao
              tipo="perigo"
              onClick={() => {
                void aplicarEEmpilhar([]);
                setLiberarTudo(false);
              }}
            >
              Tirar as {total}
            </Botao>
          </>
        }
      >
        <p>
          As {total} tarjas saem de <strong className="text-on-surface">{arquivo.originalName}</strong>,
          e o texto salvo passa a ser igual ao original — com os dados pessoais em claro.
        </p>
        <p className="mt-2">
          Nenhum termo é gravado na lista de liberados: outros documentos continuam sendo
          mascarados normalmente. Ctrl+Z desfaz.
        </p>
      </Dialogo>

      <Dialogo
        aberto={salvarSemMascara}
        aoFechar={() => setSalvarSemMascara(false)}
        titulo="Salvar sem nenhuma tarja"
        acoes={
          <>
            <Botao tipo="secundario" onClick={() => setSalvarSemMascara(false)}>
              Cancelar
            </Botao>
            <Botao
              tipo="perigo"
              onClick={() => {
                setSalvarSemMascara(false);
                aoSalvarTodos();
              }}
            >
              Salvar assim mesmo
            </Botao>
          </>
        }
      >
        <p>
          Este documento não tem tarja nenhuma. O arquivo salvo —{" "}
          <strong className="text-on-surface">{saida}</strong> — vai ter o mesmo conteúdo do
          original, e a cópia no cofre também.
        </p>
        <p className="mt-2">
          Faz sentido quando o motor não encontrou nada e você conferiu que não há mesmo dado
          pessoal. Não faz, se você tirou as tarjas para adiantar o trabalho.
        </p>
      </Dialogo>
    </div>
  );
}
