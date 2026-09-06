import { useEffect, useMemo, useRef, useState } from "react";

import { useConversa } from "../hooks/useConversa";
import { Markdown, type MapaDeNomes } from "../componentes/Markdown";
import { SeletorDeDocumentos } from "../componentes/SeletorDeDocumentos";
import { Botao, Campo, Dialogo, Icone, Selo, Tecla } from "../ui";

/**
 * Conversar com os autos — a tela de chat.
 *
 * ## É o único lugar do produto onde dado sai desta máquina
 *
 * Tudo mais acontece localmente. Aqui o texto **anonimizado** vai para um
 * modelo na nuvem, o que a Resolução CNJ 615/2025 permite justamente porque
 * está anonimizado. A referência de desenho põe no rodapé desta tela
 * "processamento sigiloso 100% local · sem upload para nuvem" e chama o modelo
 * de "local" — as duas coisas são o contrário do que acontece, e num produto
 * de sigilo essa é a pior frase possível de escrever. O rodapé daqui diz o
 * provedor, o modelo e que o texto sai.
 *
 * ## A barra lateral lista o que existe, e o que existe morre com o app
 *
 * As sessões vivem na memória do processo principal. Isso é decisão de
 * privacidade, não limitação técnica: gravar as perguntas de um magistrado
 * sobre autos sigilosos criaria em disco justamente o índice pesquisável que o
 * produto existe para não criar. A lista diz isso onde o usuário a lê.
 *
 * ## O campo está sempre à vista
 *
 * Como em qualquer chat que a pessoa já use: a área de texto fica presa ao
 * rodapé, a conversa rola por cima. O estado vazio ocupa o meio com o convite
 * e as sugestões, e o campo já está lá embaixo, pronto.
 */

interface ConversaProps {
  /** Os documentos escolhidos, por id do cofre. `null` = nenhum ainda. */
  ids: string[] | null;
  /** Tudo o que há no cofre, para o seletor e para os nomes nos chips. */
  documentos: EntradaDoCofre[];
  aoEscolherDocumentos: (ids: string[]) => void;
  aoIrParaAjustes: () => void;
  temChave: boolean;
  /** Modelo preferido, do catálogo. `null` = o padrão. */
  modelo: string | null;
  /** Retomar uma sessão de outro modelo exige mudar a preferência junto. */
  aoTrocarModelo: (modelo: string) => void;
  avisar: (mensagem: string, tipo?: "sucesso" | "erro") => void;
}

/**
 * O texto como ele trafegou: com os pseudônimos, não com os nomes repostos.
 *
 * É a forma canônica de um turno aqui. O que a tela mostra é uma leitura dela
 * — a reposição acontece na renderização, contra o mapa, e nunca no dado.
 */
function textoComRotulos(trechos: TrechoDaConversa[]): string {
  return trechos.map((t) => (t.tipo === "texto" ? t.texto : t.rotulo)).join("");
}

/** O que cada rótulo quer dizer, extraído dos trechos já resolvidos. */
function mapaDeNomes(trechos: TrechoDaConversa[]): MapaDeNomes {
  const mapa: MapaDeNomes = new Map();
  for (const t of trechos) {
    if (t.tipo === "reposto") mapa.set(t.rotulo, t.valor);
    else if (t.tipo === "desconhecido") mapa.set(t.rotulo, null);
  }
  return mapa;
}

/**
 * Quanto tempo esta resposta está demorando.
 *
 * Não é enfeite. O contexto aqui pode ter centenas de milhares de tokens, e o
 * primeiro pedaço leva de segundos a meio minuto para chegar — tempo suficiente
 * para alguém concluir que travou e fechar a tela. Três bolinhas dizem "espere"
 * e não dizem por quanto; um número que anda diz que a coisa está viva.
 */
function useCronometro(ativo: boolean): number {
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    if (!ativo) {
      setSegundos(0);
      return;
    }
    const inicio = Date.now();
    const timer = setInterval(() => setSegundos(Math.floor((Date.now() - inicio) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [ativo]);

  return segundos;
}

function Copiar({ trechos }: { trechos: TrechoDaConversa[] }) {
  const [copiado, setCopiado] = useState(false);

  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard.writeText(textoComRotulos(trechos));
        setCopiado(true);
        setTimeout(() => setCopiado(false), 1600);
      }}
      /* A tela mostra "João da Silva" para quem está aqui, com a máquina
         trancada. O que sai por Ctrl+C vai para lugar nenhum sabido — um
         e-mail, um documento — e ali o nome real não deveria estar. Copia-se o
         que de fato trafegou. */
      title="Copia com os pseudônimos, como trafegou"
      aria-label="Copiar este turno"
      className={[
        "grid size-7 place-items-center rounded-sm transition-colors duration-[120ms]",
        copiado
          ? "text-secondary"
          : "text-outline hover:bg-surface-container hover:text-on-surface",
      ].join(" ")}
    >
      <Icone nome={copiado ? "check" : "content_copy"} tamanho={16} />
    </button>
  );
}

/** O avatar do aplicativo, ao lado de cada resposta. */
function AvatarDoApp({ grande = false }: { grande?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={[
        "grid shrink-0 place-items-center rounded-full bg-secondary-container text-on-secondary-container shadow-sm",
        grande ? "size-12" : "mt-1 size-8",
      ].join(" ")}
    >
      <Icone nome="neurology" tamanho={grande ? 26 : 18} />
    </span>
  );
}

const SUGESTOES = [
  "Resuma este processo em dez linhas.",
  "Quem são as partes e quem representa cada uma?",
  "Que prazos e datas aparecem, e o que vence primeiro?",
];

const ATALHOS = [
  { rotulo: "/resumo", texto: "Resuma este processo em dez linhas." },
  { rotulo: "/partes", texto: "Quem são as partes e quem representa cada uma?" },
  { rotulo: "/prazos", texto: "Que prazos e datas aparecem, e o que vence primeiro?" },
  {
    rotulo: "/contradições",
    texto: "Há contradições entre os depoimentos e as demais peças? Cite o documento de cada uma.",
  },
];

/** "Hoje", "Ontem", "Semana passada" — a agenda mental de quem trabalha. */
function grupoDaData(iso: string): string {
  const agora = new Date();
  const quando = new Date(iso);
  const dia = 24 * 60 * 60 * 1000;
  const meiaNoite = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate()).getTime();
  if (quando.getTime() >= meiaNoite) return "Hoje";
  if (quando.getTime() >= meiaNoite - dia) return "Ontem";
  if (quando.getTime() >= meiaNoite - 7 * dia) return "Últimos 7 dias";
  return "Antes";
}

function horaCurta(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function Conversa({
  ids,
  documentos,
  aoEscolherDocumentos,
  aoIrParaAjustes,
  temChave,
  modelo,
  aoTrocarModelo,
  avisar,
}: ConversaProps) {
  const {
    estado,
    erro,
    abrindo,
    sessoes,
    perguntar,
    cancelar,
    reiniciar,
    fecharSessao,
    renomearSessao,
    previsualizar,
    orcamento,
  } = useConversa(ids, modelo);
  const [pergunta, setPergunta] = useState("");
  const [previa, setPrevia] = useState<string | null>(null);
  const [escolhendo, setEscolhendo] = useState(false);
  const [recomecando, setRecomecando] = useState(false);
  const [aFechar, setAFechar] = useState<ResumoDaConversa | null>(null);
  const [avisosAbertos, setAvisosAbertos] = useState(false);
  const [buscaSessao, setBuscaSessao] = useState("");
  const [renomeando, setRenomeando] = useState<string | null>(null);
  const [gavetaAberta, setGavetaAberta] = useState(false);
  const [custo, setCusto] = useState<Awaited<ReturnType<typeof orcamento>> | null>(null);

  const rolagem = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);
  /* Só acompanha o fim enquanto o leitor está no fim. Rolou para reler algo
     lá em cima, a resposta continua chegando sem puxar a página de volta —
     que é o comportamento mais irritante de um chat que escreve sozinho. */
  const coladoNoFim = useRef(true);

  const enviando = estado?.enviando ?? false;
  const segundos = useCronometro(enviando);

  useEffect(() => {
    void orcamento().then(setCusto);
  }, [orcamento, estado?.id]);

  useEffect(() => {
    if (!coladoNoFim.current) return;
    const caixa = rolagem.current;
    if (caixa) caixa.scrollTop = caixa.scrollHeight;
  }, [estado?.turnos.length, estado?.parcial.length, enviando]);

  /* O campo cresce com o texto até um teto, e volta ao mínimo quando esvazia. */
  useEffect(() => {
    const el = campo.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [pergunta]);

  const escolhidos = useMemo(() => {
    const porId = new Map(documentos.map((d) => [d.id, d]));
    return (ids ?? []).map((id) => porId.get(id)).filter((d): d is EntradaDoCofre => !!d);
  }, [ids, documentos]);

  const semDocumentos = ids === null || ids.length === 0;
  const bloqueada = estado?.comprometida ?? false;
  const podeEnviar = temChave && !semDocumentos && !bloqueada && !abrindo && estado !== null;
  const avisos = estado?.avisos ?? [];
  const graves = avisos.filter((a) => a.grave);
  const leves = avisos.filter((a) => !a.grave);
  const vazia = (estado?.turnos.length ?? 0) === 0;

  const enviar = () => {
    const texto = pergunta.trim();
    if (!texto || enviando || !podeEnviar) return;
    setPergunta("");
    coladoNoFim.current = true;
    void perguntar(texto);
  };

  /**
   * Retomar uma sessão da lista.
   *
   * Troca a seleção **e o modelo**: a sessão foi aberta num modelo, e a chave
   * que o hook usa para retomar em vez de reabrir inclui o modelo. Sem trocar,
   * clicar numa conversa de outro modelo abriria uma terceira, do zero, com o
   * mesmo aspecto de ter retomado.
   */
  const retomar = (sessao: ResumoDaConversa) => {
    if (sessao.modelo !== modelo) aoTrocarModelo(sessao.modelo);
    aoEscolherDocumentos(sessao.documentos.map((d) => d.id));
  };

  /**
   * Exporta a conversa em markdown, **com os pseudônimos**.
   *
   * O mesmo motivo do botão de copiar: a tela repõe os nomes reais porque a
   * máquina está trancada; um arquivo vai para onde ninguém controla.
   */
  const exportar = async () => {
    if (!estado || estado.turnos.length === 0) return;
    const linhas = [
      `# ${estado.titulo}`,
      "",
      `Peças: ${estado.documentos.map((d) => d.nome).join(", ")}`,
      `Modelo: ${estado.modelo}${estado.provedor ? ` · ${estado.provedor}` : ""}`,
      "",
      "> Os nomes aparecem como pseudônimos, do jeito que trafegaram. Os valores",
      "> reais nunca saíram desta máquina e não estão neste arquivo.",
      "",
    ];
    for (const turno of estado.turnos) {
      linhas.push(turno.papel === "usuario" ? "## Pergunta" : "## Resposta", "");
      linhas.push(textoComRotulos(turno.trechos), "");
    }
    const texto = linhas.join("\n");
    const nome = `conversa-${new Date().toISOString().slice(0, 10)}.md`;

    if (window.electronAPI?.saveFile) {
      const pasta = await window.electronAPI.selectDirectory?.();
      if (!pasta) return;
      const sep = pasta.includes("\\") ? "\\" : "/";
      const destino = `${pasta}${pasta.endsWith(sep) ? "" : sep}${nome}`;
      const feito = await window.electronAPI.saveFile(destino, texto);
      avisar(feito?.salvo ? `Conversa salva em: ${destino}` : "Nada foi salvo.", feito?.salvo ? "sucesso" : "erro");
      return;
    }
    const url = URL.createObjectURL(new Blob([texto], { type: "text/markdown" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = nome;
    a.click();
    URL.revokeObjectURL(url);
  };

  const custoPorPergunta =
    custo &&
    `~US$ ${custo.dolares.toFixed(3)} por pergunta · ~${custo.tokensEntrada.toLocaleString("pt-BR")} tokens`;

  const sessoesVisiveis = sessoes.filter((s) =>
    buscaSessao.trim() === ""
      ? true
      : s.titulo.toLowerCase().includes(buscaSessao.trim().toLowerCase()) ||
        s.documentos.some((d) => d.nome.toLowerCase().includes(buscaSessao.trim().toLowerCase()))
  );

  const porGrupo = new Map<string, ResumoDaConversa[]>();
  for (const s of sessoesVisiveis) {
    const g = grupoDaData(s.ultimaAtividade);
    const lista = porGrupo.get(g);
    if (lista) lista.push(s);
    else porGrupo.set(g, [s]);
  }

  /* A lista aparece em dois lugares: coluna fixa a partir de 1024px e
     gaveta abaixo disso. Sem a gaveta ela sumia numa janela estreita, e com
     ela ia embora a única forma de trocar de conversa — o mesmo defeito que
     o painel de ocorrências da Revisão já teve. */
  const listaDeSessoes = (
    <>
      <div className="flex min-h-0 flex-col">
        <div className="flex flex-col gap-gutter-sm bg-surface-container-lowest/70 p-gutter-md">
          <Botao
            tipo="primario"
            icone="add"
            className="w-full"
            disabled={documentos.length === 0}
            onClick={() => setEscolhendo(true)}
          >
            Nova conversa
          </Botao>
          {sessoes.length > 1 && (
            <Campo
              rotulo="Buscar nas conversas"
              rotuloOculto
              icone="search"
              placeholder="Buscar nos diálogos…"
              value={buscaSessao}
              onChange={(e) => setBuscaSessao(e.target.value)}
            />
          )}
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-gutter-sm py-gutter-xs">
          {[...porGrupo.entries()].map(([grupo, lista]) => (
            <div key={grupo}>
              <div className="flex items-center justify-between px-gutter-sm py-1">
                <span className="font-mono text-mono-tag tracking-wider text-outline uppercase">
                  {grupo}
                </span>
                <span className="font-mono text-mono-tag text-outline-variant">
                  {lista.length} {lista.length === 1 ? "sessão" : "sessões"}
                </span>
              </div>
              <ul className="mt-1 space-y-1">
                {lista.map((s) => {
                  const ativa = s.id === estado?.id;
                  return (
                    <li key={s.id}>
                      <div
                        className={[
                          "group relative flex items-start justify-between gap-1 rounded-lg p-2.5 transition-all duration-[120ms]",
                          ativa
                            ? "bg-surface-container-lowest shadow-sm"
                            : "hover:bg-surface-container-high",
                        ].join(" ")}
                      >
                        <button
                          type="button"
                          onClick={() => retomar(s)}
                          className="flex min-w-0 flex-1 items-start gap-2.5 text-left"
                        >
                          <span
                            className={`mt-0.5 shrink-0 ${ativa ? "text-primary" : "text-outline"}`}
                          >
                            <Icone
                              nome={s.comprometida ? "block" : "forum"}
                              tamanho={18}
                              preenchido={ativa}
                            />
                          </span>
                          <span className="flex min-w-0 flex-col">
                            <span
                              className={[
                                "truncate",
                                ativa
                                  ? "font-display text-body-sm font-semibold text-primary"
                                  : "font-body text-body-sm text-on-surface",
                              ].join(" ")}
                            >
                              {s.titulo}
                            </span>
                            <span className="truncate font-mono text-mono-tag text-on-surface-variant">
                              {s.totalTurnos === 0
                                ? "sem perguntas ainda"
                                : `${s.totalTurnos} turnos · ${horaCurta(s.ultimaAtividade)}`}
                            </span>
                          </span>
                        </button>

                        <span className="flex shrink-0 items-center opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 group-focus-within:opacity-100">
                          <button
                            type="button"
                            onClick={() => setRenomeando(s.id)}
                            title="Renomear"
                            aria-label={`Renomear "${s.titulo}"`}
                            className="grid size-6 place-items-center rounded-xs text-outline hover:bg-surface-container-highest hover:text-on-surface"
                          >
                            <Icone nome="edit" tamanho={14} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setAFechar(s)}
                            title="Descartar esta conversa"
                            aria-label={`Descartar "${s.titulo}"`}
                            className="grid size-6 place-items-center rounded-xs text-outline hover:bg-error-container hover:text-on-error-container"
                          >
                            <Icone nome="delete" tamanho={14} />
                          </button>
                        </span>
                      </div>

                      {renomeando === s.id && (
                        <form
                          className="mt-1 px-2.5"
                          onSubmit={(e) => {
                            e.preventDefault();
                            const campo = e.currentTarget.elements.namedItem(
                              "titulo"
                            ) as HTMLInputElement;
                            void renomearSessao(s.id, campo.value);
                            setRenomeando(null);
                          }}
                        >
                          <input
                            name="titulo"
                            defaultValue={s.titulo}
                            autoFocus
                            onBlur={() => setRenomeando(null)}
                            aria-label="Novo nome da conversa"
                            className="w-full rounded-sm bg-surface-container-lowest px-2 py-1 font-body text-body-sm text-on-surface outline-none ring-2 ring-primary/30"
                          />
                        </form>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}

          {sessoes.length === 0 && (
            <p className="px-gutter-sm py-gutter-md font-body text-body-sm text-on-surface-variant">
              Nenhuma conversa aberta ainda.
            </p>
          )}
        </div>
      </div>

      {/* O limite escrito onde ele é lido. */}
      <div className="flex items-start gap-2 p-gutter-md">
        <span className="mt-0.5 shrink-0 text-outline">
          <Icone nome="info" tamanho={16} />
        </span>
        <p className="font-body text-body-sm leading-snug text-on-surface-variant">
          As conversas existem só enquanto o aplicativo está aberto. Nada delas é gravado em
          disco — nem aqui, nem no cofre.
        </p>
      </div>
    </>
  );

  return (
    <div className="flex h-full min-h-0">
      {/* ---------------------------------------------------------------- */}
      {/* Barra lateral de sessões                                          */}
      {/* ---------------------------------------------------------------- */}
      <aside
        aria-label="Conversas desta sessão"
        className="hidden w-[300px] shrink-0 flex-col justify-between bg-surface-container-low lg:flex"
      >
        {listaDeSessoes}
      </aside>

      {gavetaAberta && (
        <div
          className="fixed inset-0 z-100 flex bg-[var(--veu)] lg:hidden"
          onClick={(e) => {
            if (e.target === e.currentTarget) setGavetaAberta(false);
          }}
        >
          <div
            role="dialog"
            aria-label="Conversas desta sessão"
            className="flex w-[min(20rem,90vw)] flex-col justify-between bg-surface-container-low"
          >
            {listaDeSessoes}
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Conversa                                                          */}
      {/* ---------------------------------------------------------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="z-20 flex h-cabecalho shrink-0 items-center justify-between gap-gutter-md bg-surface-container-lowest/90 px-gutter-lg shadow-sm backdrop-blur">
          <div className="flex min-w-0 items-center gap-gutter-md">
            {/* Abaixo de 1024px a lista de conversas é gaveta, e este é o
                único caminho até ela. */}
            <Botao
              tipo="discreto"
              circular
              icone="menu"
              className="lg:hidden"
              aria-label="Abrir a lista de conversas"
              onClick={() => setGavetaAberta(true)}
            />
            <h1 className="min-w-0 truncate font-display text-headline-sm text-on-surface">
              {estado?.titulo ?? "Conversar com os autos"}
            </h1>
            {estado && (
              <button
                type="button"
                onClick={() => setRenomeando(estado.id)}
                title="Renomear conversa"
                aria-label="Renomear conversa"
                className="hidden shrink-0 rounded-xs p-1 text-outline hover:bg-surface-container hover:text-primary lg:block"
              >
                <Icone nome="edit" tamanho={16} />
              </button>
            )}

            <span aria-hidden="true" className="hidden h-4 w-px bg-surface-container-high md:block" />

            <div className="sem-barra hidden items-center gap-1.5 overflow-x-auto lg:flex">
              {escolhidos.map((d) => (
                <span
                  key={d.id}
                  className="inline-flex shrink-0 items-center gap-1 rounded-pill bg-surface-container px-2.5 py-1 font-mono text-mono-tag text-on-surface"
                >
                  <span className="text-primary">
                    <Icone nome="description" tamanho={14} />
                  </span>
                  <span className="max-w-[150px] truncate">{d.nome}</span>
                </span>
              ))}
              <button
                type="button"
                onClick={() => setEscolhendo(true)}
                disabled={documentos.length === 0}
                className="inline-flex shrink-0 items-center gap-1 rounded-pill bg-surface-container-low px-2.5 py-1 font-mono text-mono-tag text-primary transition-colors duration-[120ms] hover:bg-surface-container disabled:opacity-40"
              >
                <Icone nome="add" tamanho={14} />
                {escolhidos.length === 0 ? "Escolher peças" : "Trocar peças"}
              </button>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-gutter-xs">
            {/* A pílula do modelo diz **nuvem**, e não "local". É o oposto do
                que a referência de desenho escreve, e o oposto é o que é
                verdade. */}
            {estado?.modelo && (
              <span
                className="hidden items-center gap-1.5 rounded-lg bg-surface-container-low px-2.5 py-1 sm:flex"
                title="O texto anonimizado é enviado a este modelo pela internet."
              >
                <Icone nome="cloud" tamanho={14} />
                <span className="max-w-[18ch] truncate font-mono text-mono-tag text-on-surface-variant">
                  {estado.modelo}
                </span>
                <span className="font-mono text-mono-tag text-primary">nuvem</span>
              </span>
            )}
            <Botao
              tipo="discreto"
              icone="ios_share"
              disabled={!estado || estado.turnos.length === 0}
              onClick={() => void exportar()}
            >
              <span className="hidden md:inline">Exportar</span>
            </Botao>
            <Botao
              tipo="perigo"
              icone="delete_sweep"
              disabled={vazia}
              onClick={() => setRecomecando(true)}
            >
              <span className="hidden md:inline">Limpar</span>
            </Botao>
          </div>
        </header>

        <div
          ref={rolagem}
          onScroll={(e) => {
            const el = e.currentTarget;
            coladoNoFim.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          }}
          className="flex-1 overflow-y-auto px-gutter-lg py-gutter-xl"
        >
          <div className="mx-auto flex w-full max-w-[820px] flex-col gap-gutter-lg">
            {(erro || estado?.erro) && (
              <p
                role="alert"
                className="rounded-lg bg-error-container/60 px-gutter-md py-gutter-sm font-body text-body-md text-on-error-container"
              >
                {erro ?? estado?.erro}
              </p>
            )}

            {graves.map((a, i) => (
              <p
                key={i}
                className="rounded-lg bg-error-container/60 px-gutter-md py-gutter-sm font-body text-body-md text-on-error-container"
              >
                <strong>Atenção: </strong>
                {a.texto}
              </p>
            ))}

            {/* Aviso leve não pode ocupar o topo da tela para sempre: são notas
                de procedência, lidas uma vez. Ficam recolhidas numa linha, com
                o número à vista para que ninguém precise adivinhar que
                existem. */}
            {leves.length > 0 && (
              <div className="rounded-lg bg-surface-container-low/70 px-gutter-md py-2.5 shadow-sm">
                <button
                  type="button"
                  onClick={() => setAvisosAbertos((v) => !v)}
                  aria-expanded={avisosAbertos}
                  className="flex w-full items-center justify-between gap-2 font-mono text-mono-tag text-outline hover:text-on-surface"
                >
                  <span className="flex items-center gap-2">
                    <Icone
                      nome="arrow_right"
                      tamanho={16}
                      className={avisosAbertos ? "rotate-90 transition-transform" : "transition-transform"}
                    />
                    {leves.length} nota{leves.length > 1 ? "s" : ""} sobre a procedência dos
                    documentos
                  </span>
                  <Selo tom="deferido">verificado</Selo>
                </button>
                {avisosAbertos && (
                  <ul className="space-y-2 pt-3 pb-1">
                    {leves.map((a, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 font-body text-body-sm text-on-surface-variant"
                      >
                        <span className="mt-0.5 shrink-0 text-secondary">
                          <Icone nome="check_circle" tamanho={16} />
                        </span>
                        {a.texto}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {vazia && !abrindo && !erro && (
              <div className="flex min-h-[42vh] flex-col items-center justify-center py-gutter-xl text-center">
                <AvatarDoApp grande />
                <h2 className="mt-gutter-md font-display text-headline-lg text-on-surface">
                  Conversar com os autos
                </h2>

                {!temChave ? (
                  <>
                    <p className="mt-3 max-w-md font-body text-body-md leading-relaxed text-on-surface-variant">
                      A conversa usa o OpenRouter e precisa de uma credencial sua, guardada cifrada
                      nesta máquina. Sem ela, o aplicativo não fala com a internet.
                    </p>
                    <Botao tipo="primario" className="mt-gutter-lg" icone="key" onClick={aoIrParaAjustes}>
                      Colar a chave nos Ajustes
                    </Botao>
                  </>
                ) : semDocumentos ? (
                  <>
                    <p className="mt-3 max-w-lg font-body text-body-md leading-relaxed text-on-surface-variant">
                      Escolha peças do cofre. O que sai desta máquina é o{" "}
                      <strong className="text-on-surface">texto anonimizado</strong> — nomes, CPFs e
                      endereços já substituídos por pseudônimos —, e só para modelos com{" "}
                      <strong className="text-on-surface">retenção zero</strong>, como a Resolução
                      CNJ 615/2025 exige. Os nomes reais voltam só aqui na tela.
                    </p>
                    <Botao
                      tipo="primario"
                      className="mt-gutter-lg"
                      icone="folder_supervised"
                      onClick={() => setEscolhendo(true)}
                      disabled={documentos.length === 0}
                    >
                      Escolher documentos
                    </Botao>
                    {documentos.length === 0 && (
                      <p className="mt-3 font-mono text-mono-tag text-outline">
                        O cofre está vazio. Anonimize um documento e guarde-o para conversar.
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    <p className="mt-3 max-w-lg font-body text-body-md leading-relaxed text-on-surface-variant">
                      {escolhidos.length === 1
                        ? "Um documento carregado."
                        : `${escolhidos.length} documentos carregados, com um espaço de pseudônimos comum.`}{" "}
                      A anonimização mede{" "}
                      <strong className="text-on-surface">99,97% por ocorrência</strong> no gate do
                      produto — alta, e não 100%.{" "}
                      <button
                        type="button"
                        onClick={() => void previsualizar().then(setPrevia)}
                        className="text-primary underline decoration-primary/40 underline-offset-4 hover:decoration-primary"
                      >
                        Veja o que sai
                      </button>{" "}
                      antes de perguntar.
                    </p>
                    <ul className="mt-gutter-lg flex flex-wrap justify-center gap-2">
                      {SUGESTOES.map((s) => (
                        <li key={s}>
                          <button
                            type="button"
                            onClick={() => {
                              setPergunta(s);
                              campo.current?.focus();
                            }}
                            className="rounded-pill bg-surface-container-lowest px-3.5 py-1.5 font-body text-body-sm text-on-surface-variant shadow-sm transition-colors duration-[120ms] hover:text-primary"
                          >
                            {s}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            {abrindo && (
              <p className="flex items-center gap-2 font-mono text-mono-tag text-outline">
                <span className="inline-block h-[1em] w-[0.45em] animate-pulse bg-primary" />
                Preparando os documentos…
              </p>
            )}

            {estado?.turnos.map((turno, i) => {
              const nomes = mapaDeNomes(turno.trechos);
              const texto = textoComRotulos(turno.trechos);

              if (turno.papel === "usuario") {
                return (
                  <article key={i} className="group flex flex-col items-end gap-1.5">
                    <div className="max-w-[80%] rounded-xl rounded-tr-xs bg-primary px-4 py-3 text-on-primary shadow-sm">
                      {/* Sem `<p>` em volta: `Markdown` já emite blocos, e um
                          `<div>` dentro de `<p>` é HTML inválido. */}
                      <Markdown texto={texto} nomes={nomes} />
                    </div>
                    <div className="flex items-center gap-1 font-mono text-mono-tag text-outline">
                      <span>Você</span>
                      <Copiar trechos={turno.trechos} />
                    </div>
                    {turno.trocas && turno.trocas.length > 0 && (
                      <p className="max-w-[80%] text-right font-mono text-mono-tag leading-relaxed text-outline">
                        trocado antes de sair:{" "}
                        {turno.trocas.map((t) => `"${t.valor}" → ${t.rotulo}`).join(" · ")}
                      </p>
                    )}
                  </article>
                );
              }

              return (
                <article key={i} className="group flex items-start gap-3">
                  <AvatarDoApp />
                  <div className="min-w-0 flex-1 rounded-xl rounded-tl-xs bg-surface-container-lowest p-gutter-lg shadow-md">
                    <div className="mb-gutter-sm flex items-center justify-between gap-2">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="font-display text-body-sm font-bold text-primary">
                          Sigilo
                        </span>
                        {estado?.modelo && (
                          <span className="truncate rounded-xs bg-surface-container px-1.5 py-0.5 font-mono text-mono-tag text-outline">
                            {estado.modelo}
                          </span>
                        )}
                      </span>
                      <Copiar trechos={turno.trechos} />
                    </div>
                    <Markdown texto={texto} nomes={nomes} />
                  </div>
                </article>
              );
            })}

            {/* A resposta chegando, e — antes dela — a prova de que está vindo. */}
            {enviando && (
              <article className="flex items-start gap-3">
                <AvatarDoApp />
                <div className="min-w-0 flex-1 rounded-xl rounded-tl-xs bg-surface-container-lowest p-gutter-lg shadow-md">
                  <div className="mb-gutter-sm flex items-center gap-2">
                    <span className="font-mono text-mono-tag text-outline tabular-nums">
                      {estado && estado.parcial.length > 0
                        ? `escrevendo · ${segundos}s`
                        : `consultando ${estado?.modelo ?? "o modelo"} · ${segundos}s`}
                    </span>
                    <button
                      type="button"
                      onClick={cancelar}
                      className="font-mono text-mono-tag text-outline underline underline-offset-2 hover:text-error"
                    >
                      parar
                    </button>
                  </div>
                  {estado && estado.parcial.length > 0 ? (
                    <Markdown
                      texto={textoComRotulos(estado.parcial)}
                      nomes={mapaDeNomes(estado.parcial)}
                      cursor
                    />
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="inline-block h-[1em] w-[0.45em] animate-pulse bg-primary" />
                      <span className="font-body text-body-md italic text-outline">
                        lendo os documentos
                      </span>
                    </div>
                  )}
                </div>
              </article>
            )}
          </div>
        </div>

        {/* -------------------------------------------------------------- */}
        {/* Compositor                                                      */}
        {/* -------------------------------------------------------------- */}
        <div className="shrink-0 px-gutter-lg pt-gutter-xs pb-gutter-md">
          <div className="mx-auto w-full max-w-[820px]">
            {/* A saída fica AQUI, fora do compositor: bloqueada, a moldura
                inteira recebe `opacity-50`, e um botão só lá dentro apareceria
                apagado justamente no caso em que ele é a única porta. */}
            {bloqueada && (
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-error-container/50 px-gutter-md py-gutter-sm">
                <p className="font-body text-body-sm text-on-error-container">
                  Esta conversa foi marcada como comprometida e não aceita novos envios.
                </p>
                <Botao icone="restart_alt" onClick={() => setRecomecando(true)}>
                  Começar outra
                </Botao>
              </div>
            )}

            {!vazia && podeEnviar && (
              <div className="sem-barra mb-gutter-xs flex items-center gap-1.5 overflow-x-auto">
                <span className="flex shrink-0 items-center gap-1 pr-1 font-mono text-mono-tag text-outline">
                  <Icone nome="bolt" tamanho={14} />
                  atalhos
                </span>
                {ATALHOS.map((a) => (
                  <button
                    key={a.rotulo}
                    type="button"
                    onClick={() => {
                      setPergunta(a.texto);
                      campo.current?.focus();
                    }}
                    className="shrink-0 rounded-pill bg-surface-container-low px-2.5 py-1 font-mono text-mono-tag text-on-surface-variant transition-colors duration-[120ms] hover:bg-surface-container hover:text-on-surface"
                  >
                    {a.rotulo}
                  </button>
                ))}
              </div>
            )}

            <div
              className={[
                "rounded-xl bg-surface-container-lowest shadow-sm transition-shadow duration-[120ms]",
                "focus-within:shadow-md focus-within:ring-2 focus-within:ring-primary/20",
                bloqueada ? "opacity-50" : "",
              ].join(" ")}
            >
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  enviar();
                }}
                className="flex items-end gap-2 p-gutter-md"
              >
                <textarea
                  ref={campo}
                  value={pergunta}
                  onChange={(e) => setPergunta(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      enviar();
                    }
                  }}
                  rows={1}
                  disabled={!podeEnviar}
                  placeholder={
                    !temChave
                      ? "Cole a chave nos Ajustes para conversar"
                      : semDocumentos
                        ? "Escolha os documentos para começar"
                        : "Pergunte aos autos anonimizados…"
                  }
                  aria-label="Pergunta"
                  className="max-h-[200px] min-h-[28px] flex-1 resize-none bg-transparent px-1 py-1 font-body text-body-lg leading-relaxed text-on-surface placeholder:text-outline focus:outline-none disabled:cursor-not-allowed"
                />
                {enviando ? (
                  <Botao
                    tipo="secundario"
                    circular
                    icone="stop"
                    aria-label="Parar a resposta"
                    onClick={cancelar}
                  />
                ) : (
                  <Botao
                    tipo="primario"
                    circular
                    icone="send"
                    type="submit"
                    aria-label="Enviar"
                    disabled={!podeEnviar || pergunta.trim() === ""}
                  />
                )}
              </form>
            </div>

            {/* O rodapé mais importante do produto. Onde a referência de
                desenho escreve "processamento sigiloso 100% local · sem upload
                para nuvem", aqui está o contrário, porque o contrário é o que
                acontece. */}
            <div className="mt-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-1 font-mono text-mono-tag text-outline">
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="flex items-center gap-1 text-on-surface-variant">
                  <Icone nome="cloud" tamanho={14} />
                  o texto anonimizado sai desta máquina
                </span>
                {estado?.provedor && (
                  <Selo tom={bloqueada ? "perigo" : "neutro"}>{estado.provedor}</Selo>
                )}
                {custoPorPergunta && <span>{custoPorPergunta}</span>}
                {estado && estado.gastoDolares > 0 && (
                  <span>gasto US$ {estado.gastoDolares.toFixed(4)}</span>
                )}
                {!semDocumentos && (
                  <button
                    type="button"
                    onClick={() => void previsualizar().then(setPrevia)}
                    className="underline underline-offset-2 hover:text-on-surface"
                  >
                    ver o que sai
                  </button>
                )}
              </span>
              <span className="flex items-center gap-1.5">
                <Tecla>Enter</Tecla> envia · <Tecla>Shift+Enter</Tecla> quebra linha
              </span>
            </div>
          </div>
        </div>
      </div>

      <SeletorDeDocumentos
        aberto={escolhendo}
        documentos={documentos}
        escolhidos={ids ?? []}
        aoFechar={() => setEscolhendo(false)}
        aoConfirmar={(novos) => {
          setEscolhendo(false);
          aoEscolherDocumentos(novos);
        }}
      />

      {/* Recomeçar apaga de verdade: a conversa vive só na memória do processo
          principal e não é gravada em lugar nenhum — não há histórico para onde
          voltar. Daí a mesma cerimônia do "apagar do cofre". */}
      <Dialogo
        aberto={recomecando}
        aoFechar={() => setRecomecando(false)}
        titulo="Começar uma conversa nova"
        acoes={
          <>
            <Botao tipo="secundario" onClick={() => setRecomecando(false)}>
              Cancelar
            </Botao>
            <Botao
              tipo="perigo"
              onClick={() => {
                reiniciar();
                setPergunta("");
                setRecomecando(false);
              }}
            >
              Recomeçar
            </Botao>
          </>
        }
      >
        <p>
          As perguntas e respostas desta conversa são descartadas. Elas não ficam gravadas em lugar
          nenhum, então não há como voltar a elas depois — exporte o que quiser guardar antes de
          recomeçar.
        </p>
        <p className="mt-2">
          {escolhidos.length === 1 ? "O mesmo documento continua" : "Os mesmos documentos continuam"}{" "}
          carregado{escolhidos.length === 1 ? "" : "s"}, com pseudônimos renumerados do zero.
        </p>
      </Dialogo>

      <Dialogo
        aberto={aFechar !== null}
        aoFechar={() => setAFechar(null)}
        titulo="Descartar esta conversa"
        acoes={
          <>
            <Botao tipo="secundario" onClick={() => setAFechar(null)}>
              Cancelar
            </Botao>
            <Botao
              tipo="perigo"
              onClick={() => {
                if (aFechar) void fecharSessao(aFechar.id);
                setAFechar(null);
              }}
            >
              Descartar
            </Botao>
          </>
        }
      >
        <p>
          <strong className="text-on-surface">{aFechar?.titulo}</strong> sai da lista, com as
          perguntas e respostas dela. Como nada disso está gravado em disco, não há como voltar.
        </p>
      </Dialogo>

      <Dialogo
        aberto={previa !== null}
        aoFechar={() => setPrevia(null)}
        titulo="O que sai desta máquina"
      >
        <p className="mb-3">
          É este o conteúdo que seria enviado ao modelo. Os dados pessoais já estão substituídos
          por pseudônimos. A anonimização mede{" "}
          <strong className="text-on-surface">99,97% por ocorrência</strong> no gate do produto —
          alta, e não 100%.
        </p>
        <pre className="max-h-[50vh] overflow-auto rounded-sm bg-surface-container-low p-gutter-md font-mono text-mono-tag leading-relaxed text-on-surface-variant">
          {previa}
        </pre>
      </Dialogo>
    </div>
  );
}
