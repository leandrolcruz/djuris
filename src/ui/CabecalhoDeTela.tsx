import type { ReactNode } from "react";

/**
 * Cabeçalho de tela — sobrelinha, título, contexto e ações.
 *
 * Cada destino do trilho inventava o seu: a Mesa tinha só o título, Documentos
 * punha a busca solta à direita, Conexões improvisava um bloco de estado no
 * canto. Mesmas coisas em posições diferentes ensinam ao usuário que cada tela
 * é um lugar novo. Com um cabeçalho só, o título está sempre no mesmo canto, e
 * o que a tela oferece está sempre à direita dele.
 *
 * A `sobrelinha` é a faixa de selos que o desenho põe acima do título — "motor
 * local zero-egress", a base normativa, o estado do cofre. Ela existe porque o
 * produto precisa afirmar onde o dado está antes de o usuário começar a
 * trabalhar, e não depois.
 *
 * O subtítulo é curto: uma contagem, um estado. Explicação longa vai no corpo.
 */

interface CabecalhoDeTelaProps {
  titulo: string;
  sobrelinha?: ReactNode;
  subtitulo?: ReactNode;
  /** Controles alinhados à direita, na linha do título. */
  acoes?: ReactNode;
  /** Título de destaque (`text-display`) — só na tela de entrada. */
  grande?: boolean;
  className?: string;
}

export function CabecalhoDeTela({
  titulo,
  sobrelinha,
  subtitulo,
  acoes,
  grande = false,
  className = "",
}: CabecalhoDeTelaProps) {
  return (
    <header
      className={[
        "flex flex-col justify-between gap-gutter-md md:flex-row md:items-end",
        className,
      ].join(" ")}
    >
      <div className="flex min-w-0 flex-col gap-gutter-xs">
        {sobrelinha && <div className="flex flex-wrap items-center gap-gutter-xs">{sobrelinha}</div>}
        <h1
          className={
            grande
              ? "font-display text-display text-on-surface"
              : "font-display text-headline-lg text-on-surface"
          }
        >
          {titulo}
        </h1>
        {subtitulo && (
          <div className="font-body text-body-md text-on-surface-variant">{subtitulo}</div>
        )}
      </div>
      {acoes && <div className="flex shrink-0 flex-wrap items-center gap-gutter-sm">{acoes}</div>}
    </header>
  );
}
