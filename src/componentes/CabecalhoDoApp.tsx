import type { ReactNode } from "react";
import { Icone } from "../ui";
import type { Tema } from "../hooks/usePreferencias";

/**
 * Cabeçalho do aplicativo — 64px, breadcrumb à esquerda, estado à direita.
 *
 * ## Ele é a moldura da janela
 *
 * O Electron sobe com `titleBarStyle: "hidden"`: não existe barra do sistema,
 * só os três controles de janela desenhados sobrepostos ao canto superior
 * direito. Esta faixa é o que resta, e é ela que arrasta a janela
 * (`.arrasto`). Dois cuidados que não são opcionais:
 *
 * - **Todo controle aqui precisa de `.sem-arrasto`**, ou o clique vira arrasto
 *   e o botão nunca dispara.
 * - **Os últimos ~140px são dos controles do sistema.** Nada pode morar ali. A
 *   referência de desenho põe exatamente nesse ponto um cartão de usuário com
 *   avatar; aqui ele não existe (o produto não tem conta), e o espaço fica
 *   reservado.
 *
 * ## O que substituiu o que
 *
 * A referência mostra "GPU Local: RTX 4090 (31°C)" e um cartão "Vara Criminal
 * 2ª / Acesso Criptografado". Nenhum dos dois existe: o motor roda em CPU e
 * não há conta de usuário. O lugar foi ocupado pelo que o revisor de fato
 * precisa saber de relance e não cabe em nenhuma tela específica — **se o
 * cofre está cifrando** e qual tema está valendo.
 *
 * O estado do motor não vem para cá de propósito: ele já mora no pé do trilho,
 * e repeti-lo faria a informação de segurança mais importante da interface
 * virar enfeite pela repetição.
 */

interface CabecalhoDoAppProps {
  /** Nome da tela atual, segunda metade do breadcrumb. */
  titulo: string;
  tema: Tema;
  aoTrocarTema: (tema: Tema) => void;
  /**
   * `false` quando o sistema não oferece cifragem — o cofre recusa gravar.
   * `null` enquanto a resposta não chegou: dizer "indisponível" antes de saber
   * seria anunciar uma falha que talvez não exista.
   */
  cofreDisponivel: boolean | null;
  /** Preferência do usuário: guardar ou não guardar. */
  cofreLigado: boolean;
  /** Faixa de andamento do lote, quando há um rodando. */
  andamento?: ReactNode;
}

const CICLO: Record<Tema, Tema> = { sistema: "papel", papel: "noite", noite: "sistema" };
const ROTULO: Record<Tema, string> = {
  sistema: "Tema: seguindo o sistema",
  papel: "Tema: claro",
  noite: "Tema: escuro",
};
const ICONE = { sistema: "contrast", papel: "light_mode", noite: "dark_mode" } as const;

export function CabecalhoDoApp({
  titulo,
  tema,
  aoTrocarTema,
  cofreDisponivel,
  cofreLigado,
  andamento,
}: CabecalhoDoAppProps) {
  const cofre = cofreDisponivel === null
    ? { icone: "hourglass_empty", texto: "Verificando cofre", classe: "text-outline", dica: "Perguntando ao sistema se há cifragem disponível." } as const
    : !cofreDisponivel
    ? { icone: "lock_open", texto: "Cofre indisponível", classe: "text-error", dica: "O sistema não oferece cifragem; o cofre recusa gravar em vez de gravar em claro." } as const
    : cofreLigado
      ? { icone: "encrypted", texto: "Cofre cifrado", classe: "text-secondary", dica: "Conteúdo e índice cifrados com o DPAPI do Windows. Não protege contra programa malicioso rodando como você." } as const
      : { icone: "lock_open", texto: "Cofre desligado", classe: "text-on-surface-variant", dica: "Nada é guardado depois de anonimizar. A revisão não pode ser reaberta." } as const;

  return (
    <header className="arrasto z-40 flex h-cabecalho shrink-0 items-center justify-between gap-gutter-md bg-surface/85 px-gutter-lg shadow-sm backdrop-blur-xl">
      <div className="flex min-w-0 items-center gap-gutter-sm">
        <span className="hidden font-mono text-mono-code text-outline sm:inline">
          TecJustiça Sigilo
        </span>
        <span className="hidden font-mono text-mono-code text-outline-variant sm:inline">/</span>
        <h1 className="truncate font-display text-headline-sm text-on-surface">{titulo}</h1>
      </div>

      {andamento}

      {/* `pr-[140px]`: os três controles de janela do Windows são desenhados
          pelo sistema por cima deste canto. Qualquer coisa aqui fica embaixo
          deles e não recebe clique. */}
      <div className="flex shrink-0 items-center gap-gutter-sm pr-[140px]">
        <span
          title={cofre.dica}
          className={`hidden items-center gap-1.5 rounded-lg bg-surface-container-low px-gutter-sm py-1 md:flex ${cofre.classe}`}
        >
          <Icone nome={cofre.icone} tamanho={16} />
          <span className="font-mono text-mono-tag">{cofre.texto}</span>
        </span>

        <button
          type="button"
          onClick={() => aoTrocarTema(CICLO[tema])}
          title={`${ROTULO[tema]} — clique para trocar`}
          aria-label={ROTULO[tema]}
          className="sem-arrasto flex items-center gap-1 rounded-lg px-gutter-sm py-1.5 text-on-surface-variant transition-colors duration-[120ms] hover:bg-surface-container-high hover:text-on-surface"
        >
          <Icone nome={ICONE[tema]} tamanho={18} />
        </button>
      </div>
    </header>
  );
}
