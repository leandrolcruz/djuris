/**
 * Ícone.
 *
 * O sistema usa **Material Symbols Outlined**, a fonte variável, servida do
 * pacote `material-symbols` instalado localmente — o CSP da janela tem
 * `font-src 'self'` e nenhuma fonte entra pela rede. O glifo é escolhido por
 * ligadura: o texto do `<span>` é o nome do ícone.
 *
 * Antes daqui havia 22 ícones desenhados à mão como `path`. O desenho novo pede
 * setenta e poucos, com estados preenchido/vazado, e desenhar isso à mão seria
 * trocar semanas por um resultado que não bate com a referência.
 *
 * **O ícone é sempre decoração.** `aria-hidden` é fixo e não há como
 * desligá-lo: o nome acessível pertence ao elemento que envolve o ícone — o
 * botão, o link, a linha da tabela. Um ícone que "fala" duplica o rótulo no
 * leitor de tela ou, pior, é a única coisa que ele lê.
 *
 * A fonte tem quatro eixos. Dois interessam:
 *
 * - **FILL** (0/1) separa o item ativo do inativo no trilho e a conversa aberta
 *   das outras. É canal redundante à cor, nunca o único.
 * - **opsz** deve acompanhar o corpo do ícone, senão o traço fica grosso demais
 *   no pequeno e fino demais no grande. A fonte só cobre 20–48, então o valor é
 *   preso nessa faixa.
 */

/* A união é curada de propósito. Ela custa uma linha por ícone novo e paga
   isso na hora em que alguém digita `visibilty`: com `string`, a ligadura não
   casa, a fonte desenha o nome cru na tela e nada acusa o erro. */
export type NomeIcone =
  /* Navegação e casca */
  | "security"
  | "folder_supervised"
  | "forum"
  | "sync_alt"
  | "tune"
  | "menu_book"
  | "menu"
  | "person"
  | "arrow_back"
  | "arrow_forward"
  | "arrow_right"
  | "arrow_drop_down"
  | "chevron_left"
  | "chevron_right"
  | "expand_more"
  | "expand_less"
  | "unfold_more"
  | "close"
  | "more_vert"
  | "add"
  | "edit"
  | "search"
  | "refresh"
  | "open_in_new"
  /* Documento e formato */
  | "description"
  | "article"
  | "assignment"
  | "text_snippet"
  | "table_chart"
  | "image"
  | "picture_as_pdf"
  | "folder"
  | "folder_open"
  | "folder_special"
  | "drive_folder_upload"
  | "file_open"
  | "file_download"
  | "post_add"
  | "history_edu"
  | "history"
  /* Justiça */
  | "gavel"
  | "balance"
  | "account_balance"
  | "policy"
  | "record_voice_over"
  | "biotech"
  | "person_off"
  /* Sigilo e segurança */
  | "lock"
  | "lock_open"
  | "lock_reset"
  | "encrypted"
  | "shield"
  | "shield_locked"
  | "verified"
  | "verified_user"
  | "visibility"
  | "visibility_off"
  | "key"
  | "block"
  /* Estado */
  | "check"
  | "check_circle"
  | "task_alt"
  | "done"
  | "done_all"
  | "warning"
  | "error"
  | "info"
  | "hourglass_empty"
  | "progress_activity"
  | "cancel"
  /* Motor e métrica */
  | "memory"
  | "speed"
  | "neurology"
  | "psychology"
  | "token"
  | "bolt"
  | "terminal"
  /* Ações */
  | "delete"
  | "delete_sweep"
  | "content_copy"
  | "ios_share"
  | "send"
  | "stop"
  | "undo"
  | "redo"
  | "restart_alt"
  | "attach_file"
  | "filter_list"
  | "checklist"
  | "thumb_up"
  | "thumb_down"
  /* Nuvem e conexão */
  | "cloud"
  | "cloud_off"
  | "link"
  | "link_off"
  | "mail"
  /* Tema */
  | "light_mode"
  | "dark_mode"
  | "contrast";

interface IconeProps {
  nome: NomeIcone;
  /** Corpo do ícone em px. O padrão 18 é o tamanho de botão do desenho. */
  tamanho?: number;
  /** Eixo FILL. Ativo/selecionado usa o preenchido. */
  preenchido?: boolean;
  /** Eixo wght (100–700). Sobe um pouco no ícone miúdo, que some no traço fino. */
  peso?: number;
  className?: string;
}

export function Icone({
  nome,
  tamanho = 18,
  preenchido = false,
  peso,
  className = "",
}: IconeProps) {
  /* `opsz` fora de 20–48 é ignorado pela fonte, e ignorado não é neutro: o
     traço volta ao padrão do eixo, que é o errado para o corpo pedido. */
  const opsz = Math.min(48, Math.max(20, tamanho));
  const wght = peso ?? (tamanho <= 14 ? 500 : 400);

  return (
    <span
      className={`material-symbols-outlined ${className}`}
      aria-hidden="true"
      style={{
        fontSize: `${tamanho}px`,
        width: `${tamanho}px`,
        height: `${tamanho}px`,
        fontVariationSettings: `'FILL' ${preenchido ? 1 : 0}, 'wght' ${wght}, 'opsz' ${opsz}`,
      }}
    >
      {nome}
    </span>
  );
}
