import { Botao, Icone } from "../ui";

/**
 * Andamento do lote — a tela cheia e a faixa do cabeçalho.
 *
 * ## Por que existem duas
 *
 * O andamento só era desenhado dentro da Mesa, como *early return*: apertar
 * Ctrl+2 no meio de um lote fazia a tela de progresso **desaparecer**. O lote
 * continuava rodando, o trilho continuava vivo, e nada na interface dizia isso
 * — quem navegasse concluiria que tinha cancelado o próprio trabalho.
 *
 * A faixa resolve pelo lado certo: ela mora na casca, ao lado do breadcrumb, e
 * não depende de qual tela está aberta. A tela cheia continua na Mesa, porque
 * quem ficou nela quer o detalhe.
 *
 * ## O indeterminado é honesto
 *
 * Enquanto o documento está sendo aberto nem o número de páginas se sabe. Uma
 * barra parada em 0% parece travamento; o indicador rodando solto diz a
 * verdade, que é "estou trabalhando e ainda não sei quanto falta".
 */

interface AndamentoProps {
  current: number;
  total: number;
  fileName: string;
  phase?: string;
  onCancelar?: () => void;
}

export function Andamento({
  current,
  total,
  fileName,
  phase = "Analisando",
  onCancelar,
}: AndamentoProps) {
  const progresso = total > 0 ? (current / total) * 100 : 0;
  const concluido = current === total && total > 0;
  const indeterminado = total <= 0 && !concluido;

  return (
    <div className="flex h-full items-center justify-center bg-background">
      <div className="w-full max-w-md animate-fade-in px-gutter-xl text-center">
        <div className="relative mx-auto mb-gutter-xl size-28">
          <svg
            className="size-28 -rotate-90"
            viewBox="0 0 112 112"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={indeterminado ? undefined : Math.round(progresso)}
            aria-label={
              indeterminado ? `${phase}: ${fileName}` : `${phase}: ${current} de ${total}`
            }
            style={indeterminado ? { animation: "spin 1.6s linear infinite" } : undefined}
          >
            <circle cx="56" cy="56" r="48" fill="none" stroke="var(--surface-container-high)" strokeWidth="6" />
            <circle
              cx="56"
              cy="56"
              r="48"
              fill="none"
              stroke="var(--primary)"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={indeterminado ? "72 302" : `${progresso * 3.02} 302`}
              className={indeterminado ? "" : "transition-all duration-700 ease-out"}
            />
          </svg>
          {!indeterminado && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="font-display text-headline-lg text-primary tabular-nums">
                {Math.round(progresso)}%
              </span>
            </div>
          )}
        </div>

        <h2 className="font-display text-headline-lg text-on-surface" aria-live="polite">
          {concluido ? "Finalizando…" : phase}
        </h2>

        <div className="mt-gutter-md rounded-lg bg-surface-container-lowest p-gutter-md text-left shadow-sm">
          {total > 0 && (
            <div className="flex items-center justify-between font-mono text-mono-tag">
              <span className="text-on-surface-variant uppercase">progresso</span>
              <span className="text-on-surface tabular-nums">
                {current} de {total}
              </span>
            </div>
          )}
          <p className="mt-1.5 truncate font-mono text-mono-code text-primary">{fileName}</p>
        </div>

        {onCancelar && !concluido && (
          <Botao tipo="perigo" icone="close" onClick={onCancelar} className="mt-gutter-lg">
            Cancelar o lote
          </Botao>
        )}

        <p className="mt-gutter-md flex items-center justify-center gap-1.5 font-body text-body-sm text-on-surface-variant">
          <Icone nome="shield_locked" tamanho={16} />
          Documentos longos levam alguns minutos. Nada sai desta máquina.
        </p>
      </div>
    </div>
  );
}

/**
 * A mesma informação comprimida numa linha, para o cabeçalho do aplicativo.
 * Fica visível em qualquer tela — é a peça que impede "naveguei e o lote
 * sumiu".
 */
export function FaixaDeAndamento({
  current,
  total,
  fileName,
  phase = "Analisando",
}: Omit<AndamentoProps, "onCancelar">) {
  const pct = total > 0 ? Math.round((current / total) * 100) : null;

  return (
    <div
      role="status"
      className="hidden min-w-0 items-center gap-gutter-sm rounded-lg bg-surface-container-low px-gutter-sm py-1.5 lg:flex"
    >
      <span className="relative flex size-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
        <span className="relative inline-flex size-2 rounded-full bg-primary" />
      </span>
      <span className="font-display text-label text-on-surface">{phase}</span>
      <span className="max-w-[26ch] truncate font-mono text-mono-tag text-on-surface-variant">
        {fileName}
      </span>
      {pct !== null && (
        <>
          <span
            aria-hidden="true"
            className="h-1 w-24 shrink-0 overflow-hidden rounded-full bg-surface-container-high"
          >
            <span
              className="block h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </span>
          <span className="font-mono text-mono-tag text-on-surface tabular-nums">{pct}%</span>
        </>
      )}
    </div>
  );
}
