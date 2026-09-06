import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";
import { Icone, type NomeIcone } from "./Icone";

/**
 * Botão.
 *
 * Quatro tipos, e a escolha entre eles é hierarquia, não gosto:
 *
 * - **primário** é a ação que a tela existe para fazer. Um por tela, cheio de
 *   cobalto.
 * - **secundário** é a ação alternativa legítima. Superfície rebaixada, sem
 *   borda — no sistema novo a separação entre camadas é tom mais sombra.
 * - **discreto** é a ação de canto: fechar, copiar, mais opções.
 * - **perigo** apaga ou revoga. Não é preenchido: um botão vermelho sólido
 *   convida ao clique, e o que ele faz não tem volta. Vermelho só no texto, e o
 *   fundo aparece no hover, quando o ponteiro já está lá de propósito.
 *
 * A caixa é **baixa**. A versão anterior escrevia todo rótulo em caixa alta com
 * entreletra, o que dava à interface inteira um ar de painel de terminal; foi a
 * única mudança que, sozinha, mudou a impressão do produto. Caixa alta ficou
 * reservada a rótulo de seção de 12px ou menos.
 *
 * `text-body-sm` no rótulo, não `text-mono-*`: botão é estrutura, e estrutura é
 * Plus Jakarta. Mono aqui é só para dado literal.
 */

type TipoBotao = "primario" | "secundario" | "discreto" | "perigo";
type TamanhoBotao = "mini" | "normal" | "grande";

interface BotaoProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tipo?: TipoBotao;
  tamanho?: TamanhoBotao;
  icone?: NomeIcone;
  /** Ícone depois do texto — para "avançar", "abrir", "exportar". */
  iconeAoFim?: boolean;
  /** Só ícone, redondo. Exige `aria-label`. */
  circular?: boolean;
  children?: ReactNode;
  ref?: Ref<HTMLButtonElement>;
}

const POR_TIPO: Record<TipoBotao, string> = {
  primario:
    "bg-primary text-on-primary shadow-sm hover:bg-primary-hover hover:shadow-md active:scale-[0.99]",
  secundario:
    "bg-surface-container-low text-on-surface hover:bg-surface-container-high",
  discreto:
    "bg-transparent text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface",
  perigo: "bg-transparent text-error hover:bg-error-container/50",
};

const POR_TAMANHO: Record<TamanhoBotao, string> = {
  /* O piso de 28px é WCAG 2.2 (alvo mínimo de 24px) com folga. */
  mini: "min-h-7 gap-1 px-2.5 text-label",
  normal: "min-h-9 gap-1.5 px-3.5 text-body-sm",
  grande: "min-h-11 gap-2 px-gutter-lg text-headline-sm",
};

const CIRCULAR: Record<TamanhoBotao, string> = {
  mini: "size-7 p-0",
  normal: "size-9 p-0",
  grande: "size-11 p-0",
};

const CORPO_DO_ICONE: Record<TamanhoBotao, number> = { mini: 14, normal: 18, grande: 20 };

export function Botao({
  tipo = "secundario",
  tamanho = "normal",
  icone,
  iconeAoFim = false,
  circular = false,
  children,
  className = "",
  ref,
  ...resto
}: BotaoProps) {
  const corpo = CORPO_DO_ICONE[tamanho];
  const glifo = icone && <Icone nome={icone} tamanho={corpo} />;

  return (
    <button
      ref={ref}
      /* `type="button"` por padrão. O padrão do HTML é `submit`, e um botão de
         ação dentro de um `<form>` que envia sem querer é o tipo de defeito que
         só aparece em produção. */
      type={resto.type ?? "button"}
      {...resto}
      className={[
        "inline-flex shrink-0 items-center justify-center font-display font-semibold whitespace-nowrap",
        "transition-all duration-[120ms]",
        "disabled:pointer-events-none disabled:opacity-40",
        circular ? "rounded-full" : "rounded-lg",
        circular ? CIRCULAR[tamanho] : POR_TAMANHO[tamanho],
        POR_TIPO[tipo],
        className,
      ].join(" ")}
    >
      {circular ? (
        (glifo ?? children)
      ) : (
        <>
          {!iconeAoFim && glifo}
          {children}
          {iconeAoFim && glifo}
        </>
      )}
    </button>
  );
}
