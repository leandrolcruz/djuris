import { useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { Icone, type NomeIcone } from "./Icone";

/**
 * Campo de texto com rótulo, apoio e erro.
 *
 * O `useId` do React gera o par `id`/`htmlFor` sozinho. Isso não é comodidade:
 * rótulo desamarrado do controle é a falha de acessibilidade mais comum em
 * formulário, e ela não aparece em nenhum teste que não seja de leitor de tela.
 * Amarrando por construção, não há como esquecer.
 *
 * `rotuloOculto` esconde o rótulo dos olhos e **não** do leitor de tela — é o
 * caso da busca, que no desenho aparece só com o ícone de lupa e o texto de
 * exemplo. Esconder de todo mundo é que não pode.
 *
 * A moldura não tem borda: fundo rebaixado, e o foco acende trocando o fundo
 * por branco mais um anel. É a mesma gramática do resto do sistema.
 */

interface CampoProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  rotulo: string;
  rotuloOculto?: boolean;
  /** Ícone dentro da moldura, à esquerda. */
  icone?: NomeIcone;
  /** Explicação curta abaixo do campo. Some quando há erro. */
  apoio?: string;
  erro?: string;
  /** Elemento à direita dentro da moldura — atalho, botão de limpar. */
  sufixo?: ReactNode;
}

export function Campo({
  rotulo,
  rotuloOculto = false,
  icone,
  apoio,
  erro,
  sufixo,
  className = "",
  ...resto
}: CampoProps) {
  const id = useId();
  const idApoio = `${id}-apoio`;

  return (
    <div className={className}>
      <label
        htmlFor={id}
        className={
          rotuloOculto
            ? "sr-only"
            : "mb-1.5 block font-mono text-mono-tag tracking-wider text-outline uppercase"
        }
      >
        {rotulo}
      </label>

      <div
        className={[
          "flex items-center gap-2 rounded-lg px-3.5 transition-all duration-[120ms]",
          "focus-within:bg-surface-container-lowest focus-within:ring-2",
          erro
            ? "bg-error-container/40 focus-within:ring-error/30"
            : "bg-surface-container-low focus-within:ring-primary/20",
        ].join(" ")}
      >
        {icone && (
          <span className="shrink-0 text-outline">
            <Icone nome={icone} tamanho={18} />
          </span>
        )}
        <input
          id={id}
          aria-invalid={erro ? true : undefined}
          aria-describedby={apoio || erro ? idApoio : undefined}
          className="min-h-10 w-full bg-transparent font-body text-body-sm text-on-surface outline-none placeholder:text-outline"
          {...resto}
        />
        {sufixo}
      </div>

      {(erro || apoio) && (
        <p
          id={idApoio}
          role={erro ? "alert" : undefined}
          className={`mt-1.5 font-body text-body-sm ${erro ? "text-error" : "text-on-surface-variant"}`}
        >
          {erro || apoio}
        </p>
      )}
    </div>
  );
}
