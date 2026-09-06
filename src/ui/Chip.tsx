import { Icone, type NomeIcone } from "./Icone";

/**
 * Chip de filtro — rótulo, contagem e estado de seleção.
 *
 * É a fita horizontal acima da tabela do cofre: "Todos 8", "Proc. 0201848… 6",
 * "Avulsos 2". A contagem fica dentro do próprio chip porque a pergunta que
 * ela responde — "vale a pena clicar aqui?" — só faz sentido junto do rótulo.
 *
 * Um `ponto` colorido marca filtro de estado (pendente, pronto), onde a
 * categoria tem cor própria no resto da interface.
 */

interface ChipProps {
  rotulo: string;
  contagem?: number;
  ativo?: boolean;
  icone?: NomeIcone;
  /** Cor CSS do ponto indicador. Filtro de estado, não de conteúdo. */
  ponto?: string;
  onClick: () => void;
}

export function Chip({ rotulo, contagem, ativo = false, icone, ponto, onClick }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={ativo}
      className={[
        "flex shrink-0 items-center gap-1.5 rounded-pill px-3 py-1 text-label",
        "transition-colors duration-[120ms]",
        ativo
          ? "bg-surface-container font-display text-primary shadow-sm"
          : "bg-surface-container-low font-body text-on-surface-variant hover:bg-surface-container hover:text-on-surface",
      ].join(" ")}
    >
      {icone && <Icone nome={icone} tamanho={14} />}
      {ponto && (
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ backgroundColor: ponto }}
        />
      )}
      <span className="max-w-[22ch] truncate">{rotulo}</span>
      {contagem !== undefined && (
        <span
          className={[
            "rounded-pill px-1.5 py-0.5 font-mono text-mono-tag tabular-nums",
            ativo
              ? "bg-surface-container-lowest text-on-surface"
              : "bg-surface-container-lowest text-outline",
          ].join(" ")}
        >
          {contagem}
        </span>
      )}
    </button>
  );
}
