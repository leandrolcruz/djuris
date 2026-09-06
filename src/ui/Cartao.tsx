import type { ReactNode } from "react";
import { Icone, type NomeIcone } from "./Icone";

/**
 * Cartão.
 *
 * A unidade de agrupamento do sistema. **Não tem borda**, e isso é a mudança
 * estrutural da repaginação: a separação entre camadas passou a ser diferença
 * de tom mais sombra curta. `--surface-container-lowest` é branco puro sobre um
 * fundo lavanda claro; no tema escuro a relação se inverte e o cartão fica mais
 * escuro que o fundo, que é como o Material 3 trata elevação no escuro.
 *
 * `semPreenchimento` existe para a tabela sangrar até a borda do cartão — sem
 * ele a tabela ganharia uma moldura de 16px que a faz parecer encaixotada.
 */

interface CartaoProps {
  children: ReactNode;
  /** Título da seção. Aparece com um fio abaixo. */
  titulo?: string;
  /** Ícone à esquerda do título, na cor de ação. */
  icone?: NomeIcone;
  /** Uma linha explicando o que a seção faz. */
  descricao?: string;
  /** Canto superior direito — normalmente um selo ou um botão mini. */
  acao?: ReactNode;
  /** Para conteúdo que precisa encostar nas bordas (tabela, lista). */
  semPreenchimento?: boolean;
  className?: string;
}

export function Cartao({
  children,
  titulo,
  icone,
  descricao,
  acao,
  semPreenchimento = false,
  className = "",
}: CartaoProps) {
  return (
    <section
      className={`rounded-lg bg-surface-container-lowest shadow-sm ${className}`}
    >
      {(titulo || acao) && (
        <div className="flex items-start justify-between gap-3 px-gutter-md pt-gutter-md pb-gutter-sm">
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 font-display text-headline-sm text-on-surface">
              {icone && (
                <span className="text-primary">
                  <Icone nome={icone} tamanho={20} />
                </span>
              )}
              {titulo}
            </h2>
            {descricao && (
              <p className="mt-1 font-body text-body-sm text-on-surface-variant">{descricao}</p>
            )}
          </div>
          {acao && <div className="shrink-0">{acao}</div>}
        </div>
      )}

      <div className={semPreenchimento ? "" : "p-gutter-md"}>{children}</div>
    </section>
  );
}
