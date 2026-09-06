import type { ReactNode } from "react";
import { Icone, type NomeIcone } from "./Icone";

/**
 * Estado vazio — a tela sem nada ainda, dizendo o que fazer.
 *
 * Um espaço em branco é um convite, e o convite precisa estar escrito: o que
 * este lugar mostra quando tiver algo, e qual é o primeiro passo. O texto
 * explica; o botão faz. Sem tom de desculpa — vazio não é erro.
 */

interface VazioProps {
  icone?: NomeIcone;
  titulo: string;
  children?: ReactNode;
  /** Normalmente um `Botao` primário. */
  acao?: ReactNode;
  className?: string;
}

export function Vazio({ icone, titulo, children, acao, className = "" }: VazioProps) {
  return (
    <div
      className={[
        "mx-auto flex max-w-md flex-col items-center px-gutter-lg py-gutter-2xl text-center",
        className,
      ].join(" ")}
    >
      {icone && (
        <span className="mb-gutter-md grid size-14 place-items-center rounded-xl bg-surface-container text-primary">
          <Icone nome={icone} tamanho={26} />
        </span>
      )}
      <h2 className="font-display text-headline-sm text-on-surface">{titulo}</h2>
      {children && (
        <div className="mt-2 font-body text-body-md leading-relaxed text-on-surface-variant">
          {children}
        </div>
      )}
      {acao && <div className="mt-gutter-lg">{acao}</div>}
    </div>
  );
}
