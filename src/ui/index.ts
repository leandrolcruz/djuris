/**
 * Primitivas da interface.
 *
 * Antes desta camada, cada tela montava seus próprios botões, cartões e chips
 * com classes soltas — o que fazia dois botões com a mesma função terem alturas
 * diferentes e um SVG de cadeado existir em três cópias.
 *
 * A regra que atravessa todas elas é a das três vozes:
 *
 * - **Plus Jakarta Sans** (`font-display`) para estrutura: título, rótulo de
 *   botão, item de menu. É o que o aplicativo **é**.
 * - **Inter** (`font-body`) para o que se lê corrido: prosa do app, texto do
 *   processo, resposta do modelo.
 * - **JetBrains Mono** (`font-mono`) para todo dado literal: número CNJ, nome
 *   de arquivo, chip de categoria, contagem, hash, caminho, comando.
 *
 * Num revisor de tarjas, confundir o texto do aplicativo com o texto do
 * documento é o erro mais caro que existe. A terceira voz é a que mais protege
 * disso: o que está em mono é dado, e dado não é opinião do programa.
 */

export { Botao } from "./Botao";
export { CabecalhoDeTela } from "./CabecalhoDeTela";
export { Cartao } from "./Cartao";
export { Campo } from "./Campo";
export { Chip } from "./Chip";
export { Dialogo } from "./Dialogo";
export { GrupoSegmentado } from "./GrupoSegmentado";
export { Icone, type NomeIcone } from "./Icone";
export { Interruptor } from "./Interruptor";
export { LinhaDeAjuste } from "./LinhaDeAjuste";
export { Marcador } from "./Marcador";
export { Pod } from "./Pod";
export { Popover } from "./Popover";
export { Selo } from "./Selo";
export { Tabela, type ColunaTabela } from "./Tabela";
export { Tarja } from "./Tarja";
export { Tecla } from "./Tecla";
export { Vazio } from "./Vazio";
