import { useCallback, useEffect, useRef, useState } from "react";

/**
 * O estado de uma conversa, acompanhado por sondagem.
 *
 * Sondar em vez de receber eventos é escolha, não preguiça. O projeto inteiro
 * fala IPC por `invoke` — o progresso do processamento também é sondado, a cada
 * segundo, contra o backend. Manter um idioma só já valeria; aqui há um motivo
 * a mais e específico.
 *
 * A resposta chega em pedaços, e um pseudônimo pode partir entre dois deles:
 * `[PESSOA_` num, `1]` no seguinte. Quem re-hidratasse pedaço a pedaço nunca
 * casaria o rótulo, e o texto cru apareceria na tela — justamente o que o
 * recurso existe para não fazer. O processo principal acumula e devolve sempre
 * o texto inteiro já resolvido, e o problema deixa de existir.
 */

const INTERVALO_MS = 120;

/**
 * A conversa aberta sobrevive à navegação.
 *
 * Ela vive no processo principal; o que esta tela guarda é só o id. Antes, sair
 * para os Ajustes (para trocar o modelo, por exemplo) e voltar fechava a
 * conversa e abria outra do zero — a pergunta e a resposta sumiam. Com os
 * atalhos Ctrl+1…5 isso acontecia a um toque de distância.
 *
 * Depois disso, guardar **uma** só passou a ser o problema seguinte: trocar de
 * seleção fechava a anterior, e a barra lateral de conversas listaria sessões
 * que já não existem. Daí o mapa: nada é fechado ao trocar de seleção, e quem
 * limita o crescimento é o teto de sessões do processo principal, que descarta
 * a menos ativa.
 *
 * O preço disso é que "mesma seleção, mesma conversa" virou **sempre a mesma
 * conversa**: com os mesmos documentos e o mesmo modelo, nenhum caminho da
 * interface produzia uma conversa nova — nem sair da tela, nem os Ctrl+1…5.
 * E quando a trava marca a conversa como comprometida, ela recusa todo envio
 * dali em diante: a tela dizia "não aceita novos envios" sem oferecer saída
 * nenhuma. Sair do beco exigia trocar a seleção, trocar o modelo ou fechar o
 * aplicativo. Daí o `reiniciar` abaixo.
 */
const vivas = new Map<string, string>();

function chaveDe(ids: string[], modelo: string | null | undefined): string {
  return `${modelo ?? ""}|${ids.join(",")}`;
}

export function useConversa(ids: string[] | null, modelo?: string | null) {
  const [estado, setEstado] = useState<EstadoDaConversa | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [abrindo, setAbrindo] = useState(false);
  /* Recomeçar é a mesma seleção de novo, então nada nas outras dependências
     muda — é este contador que faz o efeito rodar outra vez. Ele volta a zero
     numa remontagem, e tudo bem: montar já roda o efeito, e quem decide entre
     retomar e abrir é o mapa `vivas`, que é de módulo. */
  const [ciclo, setCiclo] = useState(0);
  const [sessoes, setSessoes] = useState<ResumoDaConversa[]>([]);
  const idRef = useRef<string | null>(null);

  /** A lista da barra lateral. Vem do processo principal, que é dono dela. */
  const recarregarSessoes = useCallback(async () => {
    const api = window.electronAPI?.chat;
    if (!api?.listar) return;
    setSessoes(await api.listar().catch(() => []));
  }, []);

  /* Abre quando a seleção muda, e fecha a anterior. A conversa vive no
     processo principal; sair da tela sem fechar deixaria o mapa de pseudônimos
     de pé na memória. */
  useEffect(() => {
    const api = window.electronAPI?.chat;
    if (!api || ids === null || ids.length === 0) {
      setEstado(null);
      return;
    }

    let cancelado = false;
    const chave = chaveDe(ids, modelo);
    const idConhecido = vivas.get(chave);
    const retomavel = idConhecido !== undefined;

    /* Seleção nova: a tela esvazia antes de abrir. Sem isso, uma abertura que
       falha deixava os turnos da conversa anterior desenhados sobre um id que
       já não existia — campo habilitado, pergunta indo para lugar nenhum. */
    if (!retomavel) setEstado(null);
    setErro(null);
    setAbrindo(true);

    (async () => {
      let aberta: EstadoDaConversa | null = null;

      /* Mesma seleção de antes: retoma em vez de reabrir. Se o processo
         principal não a conhece mais (o app reiniciou), cai para abrir. */
      if (idConhecido) {
        aberta = await api.estado(idConhecido).catch(() => null);
        /* Cada `await` é um ponto em que a seleção pode ter mudado por baixo.
           Continuar depois de cancelado fecharia a conversa de outra
           seleção — a que a tela mostra agora. */
        if (cancelado) return;
        /* O processo principal não a conhece mais: o teto de sessões a
           descartou, ou o app reiniciou. Sai do mapa e abre outra. */
        if (!aberta) vivas.delete(chave);
      }

      if (!aberta) {
        aberta = await api.abrir(ids, modelo ?? undefined);
        if (cancelado) {
          /* Aberta tarde demais: já existe outra seleção (ou a tela sumiu).
             Fechar agora é o que impede a conversa órfã no processo principal
             — inclusive na dupla montagem do StrictMode em desenvolvimento. */
          void api.fechar(aberta.id);
          return;
        }
      }

      vivas.set(chave, aberta.id);
      idRef.current = aberta.id;
      setEstado(aberta);
      void recarregarSessoes();
    })()
      .catch((e: unknown) => {
        if (!cancelado) setErro(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelado) setAbrindo(false);
      });

    return () => {
      cancelado = true;
      /* Não fecha nada: as conversas ficam vivas no processo principal para
         a barra lateral poder voltar a qualquer uma. */
      idRef.current = null;
    };
  }, [ids, modelo, ciclo]);

  /* Sonda só enquanto há resposta chegando. Parado, não custa nada. */
  useEffect(() => {
    if (!estado?.enviando) return;
    const api = window.electronAPI?.chat;
    if (!api) return;

    const timer = setInterval(() => {
      const id = idRef.current;
      if (!id) return;
      void api.estado(id).then((novo) => novo && setEstado(novo));
    }, INTERVALO_MS);

    return () => clearInterval(timer);
  }, [estado?.enviando]);

  const perguntar = useCallback(async (pergunta: string) => {
    const api = window.electronAPI?.chat;
    const id = idRef.current;
    if (!api || !id) {
      setErro("a conversa não está aberta; escolha os documentos de novo");
      return;
    }

    setErro(null);
    try {
      await api.perguntar(id, pergunta);
      /* A primeira leitura logo em seguida marca `enviando`, o que liga a
         sondagem acima. Sem ela, o intervalo só começaria no próximo render. */
      const novo = await api.estado(id);
      if (novo) setEstado(novo);
      /* O título da sessão nasce da primeira pergunta: sem recarregar aqui, a
         barra lateral continuaria mostrando o nome do arquivo. */
      void recarregarSessoes();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    }
  }, [recarregarSessoes]);

  const cancelar = useCallback(() => {
    const id = idRef.current;
    if (id) void window.electronAPI?.chat.cancelar(id);
  }, []);

  /**
   * Descarta a conversa atual e abre outra com os mesmos documentos.
   *
   * Fechar aqui não é opcional. O efeito acima só fecha quando a chave muda
   * (a sessão sumiu do processo principal), e recomeçar é o caso em que ela não
   * muda: sem esta chamada, o mapa de pseudônimos da conversa velha ficaria de
   * pé no processo principal até o aplicativo morrer. `fechar` também aborta o
   * envio em curso, então recomeçar no meio de uma resposta é legítimo.
   */
  const reiniciar = useCallback(() => {
    const api = window.electronAPI?.chat;
    /* O id sai antes de qualquer limpeza — zerado primeiro, não haveria o que
       fechar. */
    const id = idRef.current;
    idRef.current = null;
    if (id) for (const [chave, vivo] of vivas) if (vivo === id) vivas.delete(chave);
    setEstado(null);
    setErro(null);
    if (api && id) void api.fechar(id);
    setCiclo((c) => c + 1);
  }, []);

  /** Fecha uma sessão da barra lateral — inclusive a que está aberta. */
  const fecharSessao = useCallback(
    async (id: string) => {
      const api = window.electronAPI?.chat;
      if (!api) return;
      for (const [chave, vivo] of vivas) if (vivo === id) vivas.delete(chave);
      await api.fechar(id);
      /* Fechando a sessão aberta, o efeito precisa rodar de novo para abrir
         outra com a mesma seleção — senão a tela fica com um id morto e o
         campo de pergunta enviando para lugar nenhum. */
      if (idRef.current === id) {
        idRef.current = null;
        setEstado(null);
        setCiclo((c) => c + 1);
      }
      await recarregarSessoes();
    },
    [recarregarSessoes]
  );

  const renomearSessao = useCallback(
    async (id: string, titulo: string) => {
      const api = window.electronAPI?.chat;
      if (!api?.renomear) return;
      await api.renomear(id, titulo);
      if (idRef.current === id) {
        const novo = await api.estado(id);
        if (novo) setEstado(novo);
      }
      await recarregarSessoes();
    },
    [recarregarSessoes]
  );

  const previsualizar = useCallback(async () => {
    const id = idRef.current;
    if (!id) return null;
    return (await window.electronAPI?.chat.previsualizar(id)) ?? null;
  }, []);

  const orcamento = useCallback(async () => {
    const id = idRef.current;
    if (!id) return null;
    return (await window.electronAPI?.chat.orcamento(id)) ?? null;
  }, []);

  return {
    estado,
    erro,
    abrindo,
    sessoes,
    perguntar,
    cancelar,
    reiniciar,
    fecharSessao,
    renomearSessao,
    previsualizar,
    orcamento,
  };
}
