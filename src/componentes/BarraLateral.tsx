import { Icone, Tecla, type NomeIcone } from "../ui";
import { Marca } from "./Marca";
import type { Destino } from "../estado/tipos";

/* Lido uma vez, no módulo: o valor não muda enquanto o programa roda, e fora
   do Electron não existe — aí é zero, porque não há botão de janela nenhum. */
const recuoDosSemaforos = window.electronAPI?.janela?.recuoDosSemaforos ?? 0;

/**
 * Trilho de operações — 240px, cinco destinos, pod de estado no pé.
 *
 * ## Por que ele nunca desmonta
 *
 * Na versão anterior, `status === "loading"` e `status === "error"` eram
 * *early-returns* antes da barra lateral: sequestravam a tela inteira e
 * deixavam o aplicativo sem navegação nenhuma durante um carregamento que
 * chega a 180 s na primeira execução com BERT. Quem abria o programa via uma
 * tela de espera sem saída, sem poder ir aos Ajustes trocar o modo do motor ou
 * às Conexões ver o que estava acontecendo.
 *
 * Aqui carregamento e erro são estado *dentro* da casca. O trilho está sempre
 * montado; só o conteúdo à direita muda.
 *
 * ## O pod de estado é segurança, não enfeite
 *
 * Quando o BERT não carrega e o motor cai para spaCy, **menos nomes e locais
 * são encontrados** — o documento sai parecendo anonimizado com o mesmo aspecto
 * de sempre. Por isso o estado do motor fica permanentemente à vista, ao lado
 * do estado da API local.
 *
 * A referência de desenho põe aqui "BERT Jurídico / ATIVO / API local · 1
 * cliente ativo / 100% processamento local". As três primeiras linhas passam a
 * dizer o que o motor **realmente** é neste momento, incluindo quando ele
 * degradou. A quarta ficou como está porque é verdade: a anonimização acontece
 * inteira nesta máquina. (A conversa com o modelo de nuvem não acontece — e é a
 * tela de Conversa que diz isso, com todas as letras.)
 *
 * ## Rail
 *
 * Abaixo de 1024px o trilho encolhe para 64px e fica só com os ícones. É a
 * regra de responsividade do próprio sistema de desenho, e a janela pode
 * chegar a 800px de largura.
 *
 * ## Atalhos
 *
 * Ctrl+1 a Ctrl+5 levam a cada destino, na ordem em que aparecem. A tecla
 * fica escrita ao lado do rótulo e aparece só quando o ponteiro passa: quem usa
 * descobre; quem não usa não lê ruído.
 */

export type EstadoMotor = "carregando" | "pronto" | "erro";

interface BarraLateralProps {
  destino: Destino;
  aoNavegar: (destino: Destino) => void;
  estadoMotor: EstadoMotor;
  /** `"transformer"`, `"spacy"` ou `"unknown"`. */
  modoNlp: string;
  /** Motor rodando degradado: o BERT não subiu e caiu para spaCy. */
  degradado: boolean;
  /** Quantos clientes pareados estão ativos. `null` = API desligada. */
  clientesConectados: number | null;
}

export const DESTINOS: { id: Destino; rotulo: string; icone: NomeIcone; titulo: string }[] = [
  { id: "mesa", rotulo: "Anonimizar", icone: "security", titulo: "Anonimizar" },
  { id: "documentos", rotulo: "Documentos", icone: "folder_supervised", titulo: "Documentos" },
  { id: "conversa", rotulo: "Conversar", icone: "forum", titulo: "Conversar com os autos" },
  { id: "conexoes", rotulo: "Conexões", icone: "sync_alt", titulo: "Conexões" },
  { id: "ajustes", rotulo: "Ajustes", icone: "tune", titulo: "Ajustes" },
];

function rotuloDoMotor(estado: EstadoMotor, modoNlp: string): string {
  if (estado === "carregando") return "Motor subindo…";
  if (estado === "erro") return "Motor fora do ar";
  if (modoNlp === "transformer") return "BERT jurídico";
  if (modoNlp === "spacy") return "spaCy leve";
  return "Motor pronto";
}

function seloDoMotor(estado: EstadoMotor, degradado: boolean) {
  if (estado === "carregando") return { texto: "SUBINDO", classe: "text-outline bg-surface-container" };
  if (estado === "erro") return { texto: "FORA", classe: "text-error bg-error-container/60" };
  if (degradado) return { texto: "LEVE", classe: "text-on-tertiary-fixed-variant bg-tertiary-fixed" };
  return { texto: "ATIVO", classe: "text-on-secondary-container bg-secondary-container/60" };
}

export function BarraLateral({
  destino,
  aoNavegar,
  estadoMotor,
  modoNlp,
  degradado,
  clientesConectados,
}: BarraLateralProps) {
  const pronto = estadoMotor === "pronto";
  const selo = seloDoMotor(estadoMotor, degradado);
  const corDoPonto = pronto
    ? degradado
      ? "bg-tertiary"
      : "bg-secondary"
    : estadoMotor === "erro"
      ? "bg-error"
      : "bg-outline animate-pulse-soft";

  return (
    <aside
      aria-label="Navegação principal"
      className="z-50 flex w-trilho-rail shrink-0 flex-col justify-between bg-surface-container-low shadow-sm lg:w-trilho"
    >
      <div className="flex min-h-0 flex-col">
        {/* A faixa da marca tem a altura do cabeçalho e arrasta a janela junto
            com ele. Sem isto, a janela ficaria imóvel por toda a coluna
            esquerda — 240 dos 1440px da largura padrão.

            O recuo à esquerda é por causa do macOS: os três semáforos ficam
            exatamente neste canto, e sem reservar espaço eles caem sobre a
            marca. Quem calcula é o preload — o renderer não aprende a regra de
            cada sistema, e fora do Electron não há botão nenhum, daí o `?? 0`. */}
        <div
          className="arrasto flex h-cabecalho shrink-0 items-center bg-surface-container-lowest/60 px-gutter-sm lg:px-gutter-md"
          style={{ paddingLeft: recuoDosSemaforos || undefined }}
        >
          <div className="lg:hidden">
            <Marca versao={__VERSAO_DO_APP__} compacta />
          </div>
          <div className="hidden lg:flex">
            <Marca versao={__VERSAO_DO_APP__} />
          </div>
        </div>

        <p className="hidden px-gutter-md pt-gutter-lg pb-gutter-xs font-mono text-mono-tag tracking-wider text-outline uppercase lg:block">
          Operações judiciais
        </p>

        <nav className="flex flex-col gap-gutter-xs px-gutter-sm pt-gutter-sm lg:pt-0">
          {DESTINOS.map((item, i) => {
            const ativo = item.id === destino;
            return (
              <button
                key={item.id}
                onClick={() => aoNavegar(item.id)}
                aria-current={ativo ? "page" : undefined}
                title={item.rotulo}
                className={[
                  "group relative flex min-h-9 w-full items-center justify-center gap-gutter-sm rounded-lg",
                  "px-gutter-sm py-gutter-sm transition-all duration-[120ms] lg:justify-start lg:px-gutter-md",
                  ativo
                    ? "bg-surface-container-lowest text-primary shadow-sm"
                    : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface",
                ].join(" ")}
              >
                {/* A barra à esquerda marca o ativo mesmo para quem não percebe
                    a diferença de fundo entre o cartão e o trilho — que é sutil
                    de propósito no resto da interface. */}
                <span
                  aria-hidden="true"
                  className={[
                    "absolute top-1/2 left-0 h-4 w-0.5 -translate-y-1/2 rounded-r bg-primary",
                    "transition-opacity duration-[120ms]",
                    ativo ? "opacity-100" : "opacity-0",
                  ].join(" ")}
                />
                <Icone nome={item.icone} tamanho={20} preenchido={ativo} />
                <span
                  className={[
                    "hidden flex-1 text-left lg:block",
                    ativo ? "font-display text-headline-sm" : "font-body text-body-sm",
                  ].join(" ")}
                >
                  {item.rotulo}
                </span>
                <Tecla className="hidden opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 group-focus-visible:opacity-100 lg:inline-flex">
                  {`Ctrl+${i + 1}`}
                </Tecla>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-gutter-sm lg:p-gutter-md">
        <div className="flex flex-col gap-gutter-xs rounded-lg bg-surface-container-lowest p-gutter-sm shadow-sm lg:p-gutter-md">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-gutter-xs">
              <span className="relative flex h-2 w-2 shrink-0" title={rotuloDoMotor(estadoMotor, modoNlp)}>
                {pronto && !degradado && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-secondary opacity-75" />
                )}
                <span className={`relative inline-flex h-2 w-2 rounded-full ${corDoPonto}`} />
              </span>
              <span className="hidden font-mono text-mono-code text-on-surface lg:inline">
                {rotuloDoMotor(estadoMotor, modoNlp)}
              </span>
            </span>
            <span
              className={`hidden rounded-xs px-1.5 py-0.5 font-mono text-mono-tag lg:inline ${selo.classe}`}
            >
              {selo.texto}
            </span>
          </div>

          {degradado && (
            /* `role="status"` para o leitor de tela anunciar a degradação
               quando ela surge — é informação de segurança, não decoração. */
            <p
              role="status"
              className="hidden font-body text-body-sm leading-snug text-tertiary lg:block"
            >
              Modelo leve: menos nomes e locais serão encontrados. Revise com atenção redobrada.
            </p>
          )}

          <p className="hidden font-mono text-mono-tag text-on-surface-variant lg:block">
            {clientesConectados === null
              ? "API local desligada"
              : `API local · ${clientesConectados} cliente${clientesConectados === 1 ? "" : "s"}`}
          </p>

          <div className="hidden items-center gap-1.5 rounded-xs bg-surface-container-low/60 p-1.5 lg:flex">
            <span className="text-secondary">
              <Icone nome="verified_user" tamanho={14} />
            </span>
            <span className="font-mono text-mono-tag text-secondary">
              Anonimização 100% local
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
