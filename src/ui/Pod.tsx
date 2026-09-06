import { Icone, type NomeIcone } from "./Icone";

/**
 * Pod de métrica — ícone em quadro, rótulo em caixa alta miúda, número grande.
 *
 * O desenho usa esta peça em dois lugares que parecem diferentes e são a mesma
 * coisa: as garantias no topo do Anonimizar ("isolamento físico", "inferência")
 * e os contadores do Documentos ("anonimizados 7/8", "mascaramentos 74 tags").
 * Uma peça só evita que as duas telas divirjam com o tempo.
 *
 * `tom` existe porque um número que afirma segurança não pode ter o mesmo peso
 * visual de um número que só conta arquivos.
 */

interface PodProps {
  icone: NomeIcone;
  /** Caixa alta miúda, em mono — o que a métrica é. */
  rotulo: string;
  /** O número ou o estado. */
  valor: string;
  /** Complemento apagado logo depois do valor: "/ 8", "tags", "por hora". */
  complemento?: string;
  tom?: "neutro" | "acao" | "selado";
}

const POR_TOM = {
  neutro: { caixa: "bg-surface-container text-on-surface-variant", valor: "text-on-surface" },
  acao: { caixa: "bg-surface-container-high text-primary", valor: "text-on-surface" },
  selado: { caixa: "bg-secondary-container/40 text-secondary", valor: "text-secondary" },
} as const;

export function Pod({ icone, rotulo, valor, complemento, tom = "acao" }: PodProps) {
  const estilo = POR_TOM[tom];
  return (
    <div className="flex items-center gap-gutter-sm rounded-lg bg-surface-container-lowest px-gutter-md py-2 shadow-sm">
      <span className={`grid size-8 shrink-0 place-items-center rounded-sm ${estilo.caixa}`}>
        <Icone nome={icone} tamanho={20} />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="font-mono text-mono-tag text-on-surface-variant uppercase">{rotulo}</span>
        <span className={`font-display text-headline-sm ${estilo.valor}`}>
          {valor}
          {complemento && (
            <span className="ml-1 font-body text-body-sm font-normal text-outline">
              {complemento}
            </span>
          )}
        </span>
      </span>
    </div>
  );
}
