import type { ReactNode } from "react";

/**
 * Selo — o chip de estado e de categoria.
 *
 * Duas formas, e elas não são intercambiáveis no desenho:
 *
 * - **`chip`** (padrão) tem canto de 2px e é o formato do dado literal: tipo de
 *   entidade, contagem, tamanho de arquivo, hash. Vive em mono.
 * - **`pilula`** tem canto de 12px e é o formato do estado: SIGILOSO, ATIVO,
 *   "Pronto para conversar". Também em mono, porque continua sendo o que a
 *   máquina afirma sobre a peça.
 *
 * O tom `entidade` sai do mapa de classes e vai por atributo `style`, porque a
 * cor vem de `corDaEntidade()`, que monta `var(--color-entity-…)` em runtime.
 * É por causa deste caminho que o CSP da janela precisa de
 * `style-src 'unsafe-inline'`.
 */

type TomSelo = "neutro" | "acao" | "perigo" | "atencao" | "deferido" | "entidade";

interface SeloProps {
  children: ReactNode;
  tom?: TomSelo;
  /** Só para `tom="entidade"`: `var(--color-entity-*)`, nunca hexadecimal. */
  cor?: string;
  /** Ponto sólido antes do texto, na cor do próprio selo. */
  comPonto?: boolean;
  forma?: "chip" | "pilula";
  className?: string;
}

const POR_TOM: Record<Exclude<TomSelo, "entidade">, string> = {
  neutro: "text-on-surface-variant bg-surface-container",
  acao: "text-on-primary-fixed-variant bg-primary-fixed",
  perigo: "text-on-error-container bg-error-container/70",
  atencao: "text-on-tertiary-fixed-variant bg-tertiary-fixed",
  deferido: "text-on-secondary-container bg-secondary-container/60",
};

export function Selo({
  children,
  tom = "neutro",
  cor,
  comPonto = false,
  forma = "chip",
  className = "",
}: SeloProps) {
  const daEntidade = tom === "entidade" && cor;

  return (
    <span
      style={
        daEntidade
          ? {
              color: cor,
              backgroundColor: `color-mix(in srgb, ${cor} 14%, transparent)`,
            }
          : undefined
      }
      className={[
        "inline-flex items-center gap-1.5 whitespace-nowrap",
        "font-mono text-mono-tag",
        forma === "pilula" ? "rounded-pill px-2.5 py-0.5" : "rounded-xs px-2 py-0.5",
        daEntidade ? "" : POR_TOM[tom as Exclude<TomSelo, "entidade">],
        className,
      ].join(" ")}
    >
      {comPonto && (
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-current"
        />
      )}
      {children}
    </span>
  );
}
