import { Icone, type NomeIcone } from "./Icone";

/**
 * Grupo segmentado — escolha de um entre poucos, sempre visíveis.
 *
 * Substitui os três pares de botões que a revisão montava à mão
 * (revisar/resultado, md/docx, papel/noite). Diferente de um `<select>`, as
 * opções ficam à vista: com duas ou três alternativas, esconder as outras atrás
 * de um clique custa mais do que o espaço economizado.
 *
 * Navegação por teclado segue o padrão de radiogroup da WAI-ARIA: **Tab entra
 * uma vez só** e as setas trocam a opção. Um grupo de rádios em que cada opção
 * é uma parada de Tab obriga quem usa teclado a passar por todas para chegar ao
 * próximo controle — por isso o `tabIndex` é 0 apenas no item ativo.
 */

interface OpcaoSegmento<T extends string> {
  valor: T;
  rotulo: string;
  icone?: NomeIcone;
  /** Vira `title` e `aria-label`, para o que o rótulo curto não explica. */
  descricao?: string;
}

interface GrupoSegmentadoProps<T extends string> {
  opcoes: readonly OpcaoSegmento<T>[];
  valor: T;
  onChange: (valor: T) => void;
  /** Nome do grupo para leitor de tela. */
  rotulo: string;
  className?: string;
}

export function GrupoSegmentado<T extends string>({
  opcoes,
  valor,
  onChange,
  rotulo,
  className = "",
}: GrupoSegmentadoProps<T>) {
  const aoTeclar = (evento: React.KeyboardEvent<HTMLButtonElement>, indice: number) => {
    const passo =
      evento.key === "ArrowRight" || evento.key === "ArrowDown"
        ? 1
        : evento.key === "ArrowLeft" || evento.key === "ArrowUp"
          ? -1
          : 0;
    if (passo === 0) return;
    evento.preventDefault();
    // Circular: da última volta para a primeira, como manda o padrão.
    const proximo = (indice + passo + opcoes.length) % opcoes.length;
    onChange(opcoes[proximo].valor);
    /* O foco acompanha a seleção: o item que acabou de ficar ativo é o único
       com `tabIndex` 0, e sem isto o foco ficava num botão que já saiu da
       ordem de Tab. */
    (evento.currentTarget.parentElement?.children[proximo] as HTMLElement | undefined)?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label={rotulo}
      className={[
        "inline-flex rounded-lg bg-surface-container-high p-1",
        className,
      ].join(" ")}
    >
      {opcoes.map((opcao, indice) => {
        const ativo = opcao.valor === valor;
        return (
          <button
            key={opcao.valor}
            role="radio"
            aria-checked={ativo}
            aria-label={opcao.descricao}
            title={opcao.descricao}
            tabIndex={ativo ? 0 : -1}
            onClick={() => onChange(opcao.valor)}
            onKeyDown={(e) => aoTeclar(e, indice)}
            /* O ativo é o cartão pousado sobre o trilho rebaixado, não um
               preenchimento de ação: escolher entre "MD" e "DOCX" não é um
               comando, é um estado. */
            className={[
              "flex min-h-8 items-center gap-1.5 rounded-sm px-4 py-1.5 text-label",
              "transition-all duration-[120ms]",
              ativo
                ? "bg-surface-container-lowest font-display text-primary shadow-sm"
                : "font-body text-on-surface-variant hover:text-on-surface",
            ].join(" ")}
          >
            {opcao.icone && <Icone nome={opcao.icone} tamanho={16} />}
            {opcao.rotulo}
          </button>
        );
      })}
    </div>
  );
}
