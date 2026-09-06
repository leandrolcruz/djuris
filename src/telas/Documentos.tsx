import { useEffect, useMemo, useRef, useState } from "react";
import { pastasDe } from "../hooks/useBiblioteca";
import {
  Botao,
  CabecalhoDeTela,
  Cartao,
  Campo,
  Chip,
  Dialogo,
  Icone,
  Marcador,
  Pod,
  Selo,
  Tabela,
  Vazio,
} from "../ui";
import type { ColunaTabela } from "../ui";
import { POLITICAS_MASCARA, rotuloDaEntidade, corDaEntidade } from "../types";

/**
 * Documentos — o cofre.
 *
 * **Tabela, não grade de cartões.** A tarefa aqui é varrer: achar um processo
 * por nome, data e contagem de ocorrências. Cartão mostra bem um item; tabela
 * compara trinta. E um índice de cartório é uma tabela.
 *
 * A numeração fala o vocabulário dos autos — "fls. 1–14", não "01 / 02 / 03".
 *
 * ## O que "validado" quer dizer
 *
 * O cofre grava assim que o processamento termina, **antes** de qualquer
 * revisão — é o que permite reabrir a revisão depois. Sem distinguir os dois
 * estados, "anonimizado pelo motor" e "anonimizado e conferido por gente"
 * pesariam o mesmo, e exportar em lote (ou mandar para a nuvem) o que ninguém
 * olhou é justamente o risco que a tela de Revisão existe para cobrir. O
 * carimbo é o `revisadoEm`, gravado quando alguém salva pela Revisão.
 *
 * ## As ações em lote ficam na barra, não presas no rodapé
 *
 * A versão anterior fazia surgir uma faixa no pé da área rolável quando havia
 * seleção. Funcionava, mas ensinava que os botões aparecem e somem. Aqui eles
 * estão sempre no mesmo lugar, desabilitados com a contagem ao lado — quem
 * marca sabe de antemão o que vai poder fazer.
 */

/* Sentinela do filtro "todos". Nomeado, e nao um espaco inicial:
   um separador invisivel se perde em edicao (esta constante chegou a
   guardar um byte NUL por causa disso, e um NUL no fonte deixa o
   parser do bundler em comportamento indefinido). O prefixo garante
   que nunca colida com um numero CNJ de verdade. */
const PASTA_TODAS = "@todas";
const PENDENTES = "@pendentes";
const CONVERSAVEIS = "@conversaveis";

const POR_PAGINA = [10, 25, 50] as const;

function dataCurta(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

/** Só `placeholder` produz pseudônimo numerado, que é o que a conversa exige. */
const conversavel = (i: EntradaDoCofre) => i.politicaMascara === "placeholder";

/**
 * Como o documento foi mascarado, dito na linguagem da tela.
 *
 * "Marcador" é o rótulo que a receita usa em `POLITICAS_MASCARA`, e repeti-lo
 * aqui é de propósito: quem escolheu "com marcador" na Mesa reconhece a mesma
 * palavra no cofre.
 *
 * Ausente significa ausente, nunca "provavelmente marcador": o documento foi
 * guardado antes de o campo existir, e supor a política é o que a conversa
 * recusa fazer.
 */
function politicaDe(item: EntradaDoCofre): { texto: string; atencao: boolean } {
  const opcao = POLITICAS_MASCARA.find((p) => p.id === item.politicaMascara);
  if (opcao) return { texto: opcao.titulo, atencao: opcao.id !== "placeholder" };
  return { texto: "máscara não registrada", atencao: true };
}

interface DocumentosProps {
  itens: EntradaDoCofre[];
  cofreDisponivel: boolean | null;
  cofreLigado: boolean;
  expurgados: number;
  aoAbrir: (item: EntradaDoCofre) => void;
  aoApagar: (id: string) => void;
  /** Abre a conversa sobre os documentos marcados. */
  aoConversar: (ids: string[]) => void;
  /** Grava os documentos marcados numa pasta escolhida na hora. */
  aoExportar: (ids: string[]) => void;
  aoIrParaMesa: () => void;
}

export function Documentos({
  itens,
  cofreDisponivel,
  cofreLigado,
  expurgados,
  aoAbrir,
  aoApagar,
  aoConversar,
  aoExportar,
  aoIrParaMesa,
}: DocumentosProps) {
  const [pasta, setPasta] = useState<string>(PASTA_TODAS);
  const [busca, setBusca] = useState("");
  const [paraApagar, setParaApagar] = useState<EntradaDoCofre | null>(null);
  const [apagarMarcados, setApagarMarcados] = useState(false);
  const [porPagina, setPorPagina] = useState<number>(25);
  const [pagina, setPagina] = useState(0);
  /* Marcados para conversar. Por id, e não por índice: a lista muda com o
     filtro de pasta e com a busca, e um índice apontaria para outro documento
     depois de qualquer uma das duas. */
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const refBusca = useRef<HTMLInputElement>(null);

  /* `/` leva o cursor para a busca, como no desenho. Fora de campo de texto,
     senão digitar uma barra num formulário roubaria o foco. */
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      const alvo = e.target as HTMLElement | null;
      if (alvo && /^(INPUT|TEXTAREA)$/.test(alvo.tagName)) return;
      if (alvo?.isContentEditable) return;
      e.preventDefault();
      refBusca.current?.focus();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, []);

  const alternar = (id: string) =>
    setMarcados((atuais) => {
      const novo = new Set(atuais);
      if (novo.has(id)) novo.delete(id);
      else novo.add(id);
      return novo;
    });

  const pastas = useMemo(() => pastasDe(itens), [itens]);

  /* Nomes que aparecem mais de uma vez. Processar o mesmo arquivo duas vezes é
     comum e legítimo — o que não é aceitável é o cofre mostrar duas linhas
     idênticas sem dizer que são homônimas. */
  const homonimos = useMemo(() => {
    const conta = new Map<string, number>();
    for (const i of itens) conta.set(i.nome, (conta.get(i.nome) ?? 0) + 1);
    return new Map([...conta].filter(([, n]) => n > 1));
  }, [itens]);

  const visiveis = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return itens.filter((i) => {
      if (pasta === "Avulsos" && i.cnj) return false;
      if (pasta === PENDENTES && i.revisadoEm) return false;
      if (pasta === CONVERSAVEIS && !conversavel(i)) return false;
      if (
        pasta !== PASTA_TODAS &&
        pasta !== "Avulsos" &&
        pasta !== PENDENTES &&
        pasta !== CONVERSAVEIS &&
        i.cnj !== pasta
      )
        return false;
      if (!termo) return true;
      return (
        i.nome.toLowerCase().includes(termo) ||
        (i.cnj?.toLowerCase().includes(termo) ?? false) ||
        Object.keys(i.porTipo).some((t) => rotuloDaEntidade(t).toLowerCase().includes(termo))
      );
    });
  }, [itens, pasta, busca]);

  /* Trocar de filtro ou de busca com a página 3 aberta mostraria uma lista
     vazia sobre um resultado que existe. */
  useEffect(() => setPagina(0), [pasta, busca, porPagina]);

  const paginas = Math.max(1, Math.ceil(visiveis.length / porPagina));
  const paginaAtual = Math.min(pagina, paginas - 1);
  const naPagina = visiveis.slice(paginaAtual * porPagina, (paginaAtual + 1) * porPagina);

  const revisados = itens.filter((i) => i.revisadoEm).length;
  const totalTags = itens.reduce((n, i) => n + i.totalOcorrencias, 0);
  const marcadosValidados = [...marcados].filter((id) =>
    itens.find((i) => i.id === id)?.revisadoEm
  );

  const colunas: ColunaTabela<EntradaDoCofre>[] = [
    {
      chave: "marcar",
      cabecalho: (
        <Marcador
          marcado={naPagina.length > 0 && naPagina.every((i) => marcados.has(i.id))}
          parcial={
            naPagina.some((i) => marcados.has(i.id)) &&
            !naPagina.every((i) => marcados.has(i.id))
          }
          aoAlternar={() =>
            setMarcados((atuais) =>
              naPagina.every((i) => atuais.has(i.id))
                ? new Set([...atuais].filter((id) => !naPagina.some((i) => i.id === id)))
                : new Set([...atuais, ...naPagina.map((i) => i.id)])
            )
          }
          rotulo="Marcar todos os documentos desta página"
        />
      ),
      estreita: true,
      render: (i) => (
        /* A célula inteira é o alvo, não só os 17 px do quadrado. Com a linha
           clicável para abrir, um alvo pequeno faz a pessoa abrir o documento
           quando queria marcá-lo. */
        <div
          className="-m-gutter-md cursor-pointer p-gutter-md"
          onClick={(e) => {
            e.stopPropagation();
            alternar(i.id);
          }}
        >
          <Marcador
            marcado={marcados.has(i.id)}
            aoAlternar={() => alternar(i.id)}
            rotulo={`Marcar ${i.nome}`}
          />
        </div>
      ),
    },
    {
      chave: "documento",
      cabecalho: "Documento / processo",
      render: (i) => {
        const politica = politicaDe(i);
        return (
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <span className="truncate font-mono text-mono-code text-on-surface">{i.nome}</span>
              {i.paginasComErro > 0 && (
                /* Página que precisava de OCR e não voltou. O texto dela não
                   está no resultado — quem revisa precisa saber antes de
                   assinar. */
                <Selo tom="perigo">
                  {`${i.paginasComErro} página${i.paginasComErro > 1 ? "s" : ""} sem OCR`}
                </Selo>
              )}
            </div>
            <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
              {i.cnj ? (
                <span className="rounded-xs bg-primary-fixed px-1.5 py-0.5 font-mono text-mono-tag text-on-primary-fixed-variant">
                  {i.cnj}
                </span>
              ) : (
                <span className="font-mono text-mono-tag text-outline">peça avulsa</span>
              )}
              <span className="font-mono text-mono-tag text-outline">
                {dataCurta(i.gravadoEm)}
                {i.totalPaginas > 0 && ` · fls. 1–${i.totalPaginas}`}
              </span>
              {/* Só "marcador" conversa; o que destoa fica em cor de atenção.
                  Descobrir isso ao abrir a conversa é tarde, então a lista diz
                  antes. */}
              {politica.atencao && <Selo tom="atencao">{politica.texto}</Selo>}
              {homonimos.has(i.nome) && (
                <Selo tom="acao">{homonimos.get(i.nome)} com este nome</Selo>
              )}
            </div>
          </div>
        );
      },
    },
    {
      chave: "tipos",
      cabecalho: "Entidades mascaradas",
      render: (i) => (
        <div className="flex flex-wrap gap-1">
          {Object.entries(i.porTipo)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
            .map(([tipo, n]) => (
              <Selo key={tipo} tom="entidade" cor={corDaEntidade(tipo)} comPonto>
                {rotuloDaEntidade(tipo)} {n}
              </Selo>
            ))}
          {Object.keys(i.porTipo).length > 3 && (
            <Selo>+{Object.keys(i.porTipo).length - 3}</Selo>
          )}
        </div>
      ),
    },
    {
      chave: "estado",
      cabecalho: "Revisão",
      estreita: true,
      render: (i) =>
        i.revisadoEm ? (
          <Selo tom="deferido" comPonto>
            validado {dataCurta(i.revisadoEm)}
          </Selo>
        ) : (
          <Selo tom="atencao" comPonto>
            pendente
          </Selo>
        ),
    },
    {
      chave: "total",
      cabecalho: "Ocorrências",
      numerica: true,
      render: (i) => i.totalOcorrencias.toLocaleString("pt-BR"),
    },
    {
      chave: "acoes",
      cabecalho: "",
      estreita: true,
      /* A linha inteira abre o documento — é o gesto que as pessoas tentam
         antes de procurar o botão. O botão fica assim mesmo: linha clicável é
         atalho para quem descobre, não substituto de um alvo visível. */
      render: (i) => (
        <div className="flex items-center gap-1 opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 focus-within:opacity-100">
          <Botao
            tamanho="mini"
            onClick={(e) => {
              e.stopPropagation();
              aoAbrir(i);
            }}
          >
            Abrir
          </Botao>
          <Botao
            tamanho="mini"
            tipo="discreto"
            circular
            icone="delete"
            aria-label={`Apagar ${i.nome}`}
            onClick={(e) => {
              e.stopPropagation();
              setParaApagar(i);
            }}
          />
        </div>
      ),
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="flex w-full flex-col gap-gutter-lg px-gutter-xl py-gutter-lg">
        <CabecalhoDeTela
          titulo="Documentos e autos"
          sobrelinha={
            cofreDisponivel === false ? (
              <Selo tom="perigo" forma="pilula" comPonto>
                COFRE INDISPONÍVEL
              </Selo>
            ) : (
              <Selo tom="deferido" forma="pilula">
                CIFRADO EM REPOUSO COM O DPAPI DO WINDOWS
              </Selo>
            )
          }
          subtitulo={
            itens.length === 0
              ? "Nada guardado ainda."
              : `${itens.length} documento${itens.length === 1 ? "" : "s"} no cofre desta máquina.`
          }
          acoes={
            itens.length > 0 && (
              <>
                <Pod
                  icone="verified"
                  rotulo="Validados"
                  valor={String(revisados)}
                  complemento={`de ${itens.length}`}
                />
                <Pod
                  icone="shield"
                  rotulo="Mascaramentos"
                  valor={totalTags.toLocaleString("pt-BR")}
                  complemento="ocorrências"
                  tom="selado"
                />
                <Botao tipo="primario" icone="add" onClick={aoIrParaMesa}>
                  Importar autos
                </Botao>
              </>
            )
          }
        />

        {cofreDisponivel === false && (
          <Cartao titulo="O cofre não pode gravar" icone="lock_open">
            <p className="font-body text-body-md text-on-surface-variant">
              O sistema não oferece cifragem para esta conta, e o cofre recusa gravar em claro.
              Documentos anonimizados continuam podendo ser salvos onde você escolher — só não
              ficam guardados aqui para reabrir.
            </p>
          </Cartao>
        )}

        {expurgados > 0 && (
          <p role="status" className="font-body text-body-sm text-on-surface-variant">
            {expurgados} documento{expurgados > 1 ? "s" : ""} saíram do cofre por terem passado
            do prazo de guarda.
          </p>
        )}

        {itens.length === 0 && cofreDisponivel !== false && (
          <Vazio
            icone="folder_supervised"
            titulo={cofreLigado ? "O cofre está vazio" : "O cofre está desligado"}
            acao={
              <Botao tipo="primario" icone="security" onClick={aoIrParaMesa}>
                Anonimizar um documento
              </Botao>
            }
          >
            {cofreLigado
              ? "Cada documento anonimizado fica guardado aqui, cifrado, para reabrir a revisão e conversar sobre ele."
              : "Nada é guardado em disco. Ao anonimizar um documento, o aplicativo pergunta se você quer guardá-lo aqui — e explica exatamente o que passa a ficar gravado."}
          </Vazio>
        )}

        {itens.length > 0 && (
          <>
            <div className="flex flex-col gap-gutter-md rounded-lg bg-surface-container-lowest p-gutter-md shadow-sm">
              <div className="flex flex-col items-stretch justify-between gap-gutter-md md:flex-row md:items-center">
                <Campo
                  ref={refBusca}
                  rotulo="Buscar no cofre"
                  rotuloOculto
                  icone="search"
                  placeholder="nome do arquivo, número do processo ou tipo de dado…"
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                  className="max-w-xl flex-1"
                  sufixo={
                    <kbd className="rounded-xs bg-surface-container-high px-1.5 py-0.5 font-mono text-mono-tag text-on-surface-variant">
                      /
                    </kbd>
                  }
                />

                <div className="flex items-center gap-gutter-xs">
                  <Botao
                    icone="forum"
                    disabled={marcados.size === 0}
                    onClick={() => aoConversar([...marcados])}
                  >
                    Conversar
                    {marcados.size > 0 && ` · ${marcados.size}`}
                  </Botao>
                  <Botao
                    icone="file_download"
                    disabled={marcadosValidados.length === 0}
                    title={
                      marcados.size > 0 && marcadosValidados.length === 0
                        ? "Nenhum dos marcados passou pela revisão."
                        : undefined
                    }
                    onClick={() => aoExportar(marcadosValidados)}
                  >
                    Exportar validados
                    {marcadosValidados.length > 0 && ` · ${marcadosValidados.length}`}
                  </Botao>
                  <Botao
                    tipo="perigo"
                    circular
                    icone="delete_sweep"
                    aria-label="Apagar os documentos marcados"
                    disabled={marcados.size === 0}
                    onClick={() => setApagarMarcados(true)}
                  />
                </div>
              </div>

              <div className="sem-barra flex items-center gap-2 overflow-x-auto">
                <span className="shrink-0 pr-1 font-mono text-mono-tag tracking-wider text-outline uppercase">
                  Filtro
                </span>
                <Chip
                  rotulo="Todos"
                  contagem={itens.length}
                  ativo={pasta === PASTA_TODAS}
                  onClick={() => setPasta(PASTA_TODAS)}
                />
                {pastas.map((p) => (
                  <Chip
                    key={p}
                    rotulo={p === "Avulsos" ? "Avulsos" : `Proc. ${p}`}
                    icone={p === "Avulsos" ? undefined : "gavel"}
                    contagem={
                      p === "Avulsos"
                        ? itens.filter((i) => !i.cnj).length
                        : itens.filter((i) => i.cnj === p).length
                    }
                    ativo={pasta === p}
                    onClick={() => setPasta(p)}
                  />
                ))}
                <Chip
                  rotulo="Pendente de validação"
                  ponto="var(--tertiary)"
                  contagem={itens.length - revisados}
                  ativo={pasta === PENDENTES}
                  onClick={() => setPasta(PENDENTES)}
                />
                <Chip
                  rotulo="Prontos para conversar"
                  ponto="var(--secondary)"
                  contagem={itens.filter(conversavel).length}
                  ativo={pasta === CONVERSAVEIS}
                  onClick={() => setPasta(CONVERSAVEIS)}
                />
              </div>
            </div>

            <Cartao semPreenchimento>
              <Tabela
                rotulo="Documentos guardados"
                colunas={colunas}
                linhas={naPagina}
                chaveDaLinha={(i) => i.id}
                aoAbrir={aoAbrir}
                vazio={
                  busca ? "Nenhum documento com esse termo." : "Nenhum documento neste filtro."
                }
              />

              {visiveis.length > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-gutter-sm bg-surface-container-low/50 px-gutter-md py-gutter-sm">
                  <span className="flex items-center gap-1.5 font-mono text-mono-tag text-on-surface-variant">
                    <span className="text-secondary">
                      <Icone nome="encrypted" tamanho={14} />
                    </span>
                    Cofre local cifrado · exibindo {paginaAtual * porPagina + 1}–
                    {paginaAtual * porPagina + naPagina.length} de {visiveis.length}
                  </span>

                  <div className="flex items-center gap-gutter-sm">
                    <label className="flex items-center gap-1.5 font-mono text-mono-tag text-on-surface-variant">
                      Linhas por página
                      <select
                        value={porPagina}
                        onChange={(e) => setPorPagina(Number(e.target.value))}
                        className="rounded-xs bg-surface-container-high px-1.5 py-0.5 font-mono text-mono-tag text-on-surface outline-none"
                      >
                        {POR_PAGINA.map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </select>
                    </label>
                    <Botao
                      tamanho="mini"
                      tipo="discreto"
                      circular
                      icone="chevron_left"
                      aria-label="Página anterior"
                      disabled={paginaAtual === 0}
                      onClick={() => setPagina((p) => Math.max(0, p - 1))}
                    />
                    <span className="font-mono text-mono-tag text-on-surface tabular-nums">
                      {paginaAtual + 1} / {paginas}
                    </span>
                    <Botao
                      tamanho="mini"
                      tipo="discreto"
                      circular
                      icone="chevron_right"
                      aria-label="Próxima página"
                      disabled={paginaAtual >= paginas - 1}
                      onClick={() => setPagina((p) => Math.min(paginas - 1, p + 1))}
                    />
                  </div>
                </div>
              )}
            </Cartao>

            {/* O limite do DPAPI escrito na tela, não escondido na
                documentação: ele protege contra outro usuário da máquina e
                contra leitura do disco fora do sistema, e **não** contra
                programa malicioso rodando como você. */}
            <div className="flex items-start gap-gutter-md rounded-lg bg-surface-container/60 p-gutter-md">
              <span className="grid size-10 shrink-0 place-items-center rounded-sm bg-surface-container-lowest text-primary">
                <Icone nome="policy" tamanho={22} />
              </span>
              <div>
                <h2 className="font-display text-headline-sm text-on-surface">
                  O que a cifragem do cofre garante
                </h2>
                <p className="mt-1 max-w-4xl font-body text-body-sm text-on-surface-variant">
                  Conteúdo e índice ficam cifrados em repouso com o DPAPI do Windows, amarrados à
                  sua conta: outro usuário da máquina não abre, e o disco lido fora do sistema
                  também não. <strong className="text-on-surface">Não protege</strong> contra
                  programa malicioso rodando como você. Nenhum documento listado aqui é enviado
                  para lugar nenhum — o envio só acontece na tela Conversar, e só com o texto já
                  anonimizado.
                </p>
              </div>
            </div>
          </>
        )}

        <Dialogo
          aberto={apagarMarcados}
          aoFechar={() => setApagarMarcados(false)}
          titulo={`Apagar ${marcados.size} documento${marcados.size > 1 ? "s" : ""} do cofre`}
          acoes={
            <>
              <Botao tipo="secundario" onClick={() => setApagarMarcados(false)}>
                Cancelar
              </Botao>
              <Botao
                tipo="perigo"
                onClick={() => {
                  for (const id of marcados) aoApagar(id);
                  setMarcados(new Set());
                  setApagarMarcados(false);
                }}
              >
                Apagar {marcados.size}
              </Botao>
            </>
          }
        >
          <p>
            {marcados.size === 1 ? "O documento sai" : "Os documentos saem"} do cofre e não{" "}
            {marcados.size === 1 ? "poderá" : "poderão"} ser
            {marcados.size === 1 ? " reaberto" : " reabertos"}. Os arquivos que você já salvou em
            disco não são afetados.
          </p>
        </Dialogo>

        <Dialogo
          aberto={paraApagar !== null}
          aoFechar={() => setParaApagar(null)}
          titulo="Apagar do cofre"
          acoes={
            <>
              <Botao tipo="secundario" onClick={() => setParaApagar(null)}>
                Cancelar
              </Botao>
              <Botao
                tipo="perigo"
                onClick={() => {
                  if (paraApagar) aoApagar(paraApagar.id);
                  setParaApagar(null);
                }}
              >
                Apagar
              </Botao>
            </>
          }
        >
          <p>
            <strong className="text-on-surface">{paraApagar?.nome}</strong> sai do cofre e não
            poderá ser reaberto. Os arquivos que você já salvou em disco não são afetados.
          </p>
        </Dialogo>
      </div>
    </div>
  );
}
