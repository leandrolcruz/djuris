import type { EntityFound } from "../types";

/**
 * Como o texto do documento vira tarjas — e por que a numeração importa tanto.
 *
 * Estas duas funções eram exportadas da tela `Revisao.tsx` e testadas de lá.
 * Vieram para cá porque são lógica pura sobre dados, sem nada de React, e
 * porque o teste que as trava não deveria depender de um módulo que importa a
 * árvore de componentes inteira.
 */

/** Segmento de texto: trecho comum ou uma ocorrência detectada. */
export type Segmento =
  | { tipo: "texto"; conteudo: string }
  | { tipo: "entidade"; conteudo: string; entidade: EntityFound; indice: number };

/**
 * Divide o texto original nos pontos onde há detecção, para que cada ocorrência
 * possa ser tarjada, focada e auditada individualmente.
 *
 * ## O índice é o da lista original, e isso não é detalhe
 *
 * `indice` tem de ser a posição da ocorrência em `entitiesFound`, **não** a
 * posição no array ordenado e filtrado daqui. A lista lateral identifica cada
 * ocorrência por `entitiesFound.indexOf(entidade)`, e o texto marca cada tarja
 * com `data-ocorrencia={indice}`: se os dois numerarem diferente, clicar numa
 * ocorrência da lista leva a **outra** tarja no texto.
 *
 * Era o que acontecia. Este `forEach` numerava pela ordem de saída, que difere
 * da original em dois momentos: quando o motor não devolve as ocorrências
 * ordenadas por `start`, e sempre que alguma é descartada — a faixa inválida no
 * `filter`, ou a sobreposta no `return` abaixo. Num documento de OCR, com
 * centenas de ocorrências e sobreposição frequente, os dois acontecem.
 *
 * Num revisor de tarjas isso é grave e silencioso: quem confere clica na
 * ocorrência 12, o texto rola até outra, e a pessoa acredita ter auditado a
 * que pediu. O erro não aparece em lugar nenhum — os dois números existem, são
 * válidos, e apontam para coisas diferentes.
 */
export function segmentar(texto: string, entidades: EntityFound[]): Segmento[] {
  const ordenadas = entidades
    // O índice original viaja junto, antes de qualquer filtro ou ordenação.
    .map((entidade, indice) => ({ entidade, indice }))
    .filter(({ entidade: e }) => e.start < e.end && e.end <= texto.length)
    .sort((a, b) => a.entidade.start - b.entidade.start);

  const segmentos: Segmento[] = [];
  let cursor = 0;

  ordenadas.forEach(({ entidade, indice }) => {
    if (entidade.start < cursor) return; // sobreposta com a anterior
    if (entidade.start > cursor) {
      segmentos.push({ tipo: "texto", conteudo: texto.slice(cursor, entidade.start) });
    }
    segmentos.push({
      tipo: "entidade",
      conteudo: texto.slice(entidade.start, entidade.end),
      entidade,
      indice,
    });
    cursor = entidade.end;
  });

  if (cursor < texto.length) {
    segmentos.push({ tipo: "texto", conteudo: texto.slice(cursor) });
  }
  return segmentos;
}

/** Uma ocorrência e a sua posição na lista original — o par que não pode se separar. */
export interface OcorrenciaIndexada {
  entidade: EntityFound;
  indice: number;
}

/**
 * Agrupa as ocorrências por tipo, na ordem em que os chips de filtro
 * apareciam: o tipo mais numeroso primeiro.
 *
 * ## O índice é capturado aqui, e é o mesmo invariante do `segmentar`
 *
 * `indice` é a posição em `entitiesFound`, capturada no `forEach` antes de
 * qualquer agrupamento ou reordenação. É o número que a tarja carrega em
 * `data-ocorrencia`, e é por ele que o clique na lista acha o trecho no texto.
 *
 * O painel obtinha esse número com `entitiesFound.indexOf(entidade)` a cada
 * linha. Funcionava — `indexOf` compara por referência —, mas é uma varredura
 * por item e depende de a lista nunca guardar o mesmo objeto duas vezes.
 * Capturar na origem não depende disso.
 *
 * A ordenação por confiança torna a garantia mais necessária, não menos: com
 * ela a posição na lista deixa de ter qualquer relação com a posição no texto,
 * e um índice deduzido da ordem de exibição apontaria para outra tarja. É o
 * defeito que o `segmentar` documenta — os dois números existem, os dois são
 * válidos, e o revisor acredita ter conferido a ocorrência que pediu.
 *
 * @param fracasPrimeiro ordena cada grupo do menor score para o maior — a
 *   pergunta "o que tem mais chance de estar errado?". Só passou a ter
 *   resposta honesta quando o score deixou de ser o máximo do tipo no
 *   documento e passou a ser o da ocorrência.
 */
export function agruparPorTipo(
  entidades: EntityFound[],
  fracasPrimeiro = false
): { tipo: string; itens: OcorrenciaIndexada[] }[] {
  const porTipo = new Map<string, OcorrenciaIndexada[]>();
  entidades.forEach((entidade, indice) => {
    const lista = porTipo.get(entidade.type);
    if (lista) lista.push({ entidade, indice });
    else porTipo.set(entidade.type, [{ entidade, indice }]);
  });

  return [...porTipo.entries()]
    .sort(([, a], [, b]) => b.length - a.length)
    .map(([tipo, itens]) => ({
      tipo,
      itens: fracasPrimeiro
        ? [...itens].sort((a, b) => a.entidade.score - b.entidade.score)
        : itens,
    }));
}
