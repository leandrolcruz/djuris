import type { CSSProperties, KeyboardEvent } from "react";
import { corDaEntidade, rotuloDaEntidade } from "../types";
import { Icone } from "./Icone";

/**
 * Tarja de redação — o elemento de assinatura do produto.
 *
 * Uma barra sólida cor de tinta cobre o dado detectado. Passar o cursor (ou dar
 * foco pelo teclado) pinta a barra com a cor do tipo e revela o valor, junto de
 * um painel que diz **o que** o motor achou, **com quanta confiança** e oferece
 * as duas decisões possíveis. É assim que o revisor confere sem desmascarar o
 * documento inteiro.
 *
 * ## O painel é a mudança de verdade
 *
 * Antes, o único jeito de saber o tipo de uma tarja era achá-la na lista
 * lateral — e a lista tem dezenas de itens. O painel traz a resposta ao lugar
 * onde a pergunta nasce.
 *
 * Ele não pode viver dentro do `<button>`: HTML não permite botão dentro de
 * botão, e as duas decisões são botões. Daí o envelope `<span>` com
 * `position: relative`, que também é `display: inline` para que um nome longo
 * continue quebrando entre linhas — a tarja é conteúdo do documento, não um
 * bloco encaixado nele.
 *
 * ## A cor
 *
 * `--cor-entidade` chega por atributo `style` porque `corDaEntidade()` monta
 * `var(--color-entity-…)` em runtime. É por causa deste caminho que o CSP da
 * janela precisa de `style-src 'unsafe-inline'`.
 */

interface TarjaProps {
  /** O texto original que a tarja esconde. */
  children: string;
  /** `CPF_BR`, `PERSON`… String livre: recognizer novo cai no cinza. */
  tipo: string;
  /** Posição na lista de ocorrências — é por ele que a lista lateral navega. */
  indice: number;
  /** Confiança do motor, 0–1. Ausente quando o dado não veio. */
  score?: number;
  ativa?: boolean;
  /** À mostra sem precisar do cursor. */
  revelada?: boolean;
  varrendo?: boolean;
  onClick?: () => void;
  /** "Não é dado pessoal" — grava na lista de termos liberados. */
  aoLiberar?: () => void;
}

/* O atraso da varredura cresce com a posição, mas com teto: num documento de
   oitocentas ocorrências, atraso proporcional viraria espetáculo de meio
   minuto antes de a tela ficar utilizável. */
const ATRASO_MAXIMO_MS = 240;
const atrasoDe = (indice: number) => Math.min(ATRASO_MAXIMO_MS, indice * 12);

export function Tarja({
  children,
  tipo,
  indice,
  score,
  ativa = false,
  revelada = false,
  varrendo = false,
  onClick,
  aoLiberar,
}: TarjaProps) {
  const cor = corDaEntidade(tipo);
  const estilo = {
    "--cor-entidade": cor,
    "--atraso": `${atrasoDe(indice)}ms`,
  } as CSSProperties;
  const rotulo = rotuloDaEntidade(tipo);
  const confianca = score === undefined ? null : `${Math.round(score * 100)}%`;

  return (
    <span className="group/tarja relative inline" style={estilo}>
      <button
        type="button"
        className="tarja"
        data-ocorrencia={indice}
        data-revelada={revelada || undefined}
        data-varrendo={varrendo || undefined}
        data-ativa={ativa || undefined}
        aria-label={`${rotulo}: ${children}`}
        onClick={onClick}
        onKeyDown={(e: KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick?.();
          }
        }}
      >
        {children}
      </button>

      {/* `pointer-events-none` enquanto escondido: sem isso o painel invisível
          intercepta o clique na linha de texto acima da tarja. */}
      <span
        role="tooltip"
        className={[
          "pointer-events-none invisible absolute bottom-full left-0 z-100 mb-2 w-72",
          "flex flex-col gap-2 rounded-lg bg-inverse-surface p-3 text-inverse-on-surface shadow-lg",
          "opacity-0 transition-opacity duration-[120ms]",
          "group-hover/tarja:pointer-events-auto group-hover/tarja:visible group-hover/tarja:opacity-100",
          "group-focus-within/tarja:pointer-events-auto group-focus-within/tarja:visible group-focus-within/tarja:opacity-100",
        ].join(" ")}
      >
        <span className="flex items-center justify-between gap-2">
          <span className="font-mono text-mono-tag uppercase" style={{ color: cor }}>
            {rotulo}
            {confianca && ` · ${confianca}`}
          </span>
          <span className="font-mono text-mono-tag opacity-70">motor local</span>
        </span>

        <span className="block font-mono text-mono-code break-all">{children}</span>

        {aoLiberar && (
          <span className="flex items-center gap-1.5">
            <span className="flex flex-1 items-center justify-center gap-1 rounded-xs bg-secondary px-2 py-1 font-display text-mono-tag text-on-secondary">
              <Icone nome="lock" tamanho={13} />
              mantido em sigilo
            </span>
            <button
              type="button"
              onClick={aoLiberar}
              className="flex-1 rounded-xs bg-surface-container-highest px-2 py-1 font-display text-mono-tag text-on-surface transition-colors duration-[120ms] hover:bg-surface-bright"
            >
              não é dado pessoal
            </button>
          </span>
        )}
      </span>
    </span>
  );
}
