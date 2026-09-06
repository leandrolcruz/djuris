/**
 * Tecla — um atalho de teclado, desenhado como a tecla que ele é.
 *
 * Aparece ao lado do destino no trilho e em dicas de campo ("Enter envia").
 * É informação secundária: apagada, pequena, nunca disputando com o rótulo.
 */

export function Tecla({ children, className = "" }: { children: string; className?: string }) {
  return (
    <kbd
      className={[
        "inline-flex min-w-5 items-center justify-center rounded-xs",
        "bg-surface-container-high px-1.5 py-0.5 font-mono text-mono-tag text-on-surface-variant",
        className,
      ].join(" ")}
    >
      {children}
    </kbd>
  );
}
