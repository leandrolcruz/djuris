import { useState } from "react";
import { InstaladorCli } from "../componentes/InstaladorCli";
import { Botao, CabecalhoDeTela, Cartao, Dialogo, Selo } from "../ui";
import type { ClientePareado } from "../hooks/usePythonBackend";

/**
 * Conexões — quem, além desta janela, alcança o motor.
 *
 * ## O pareamento, e por que ele tem um código
 *
 * Um cliente abre `POST /v1/parear` e recebe seis caracteres. Os **mesmos** seis
 * aparecem no diálogo aqui. Conferir o código nos dois lados é o que separa
 * "autorizei o programa que eu acabei de rodar" de "cliquei em permitir num
 * pedido que apareceu sozinho" — sem isso, qualquer processo local poderia
 * abrir um pedido e torcer para a pessoa aprovar no automático.
 *
 * O pedido vale 180 segundos. Curto de propósito: quem pareia está com o
 * programa aberto na frente. Um pedido que sobrevive à tarde inteira vira uma
 * aprovação distraída.
 *
 * ## O escopo que não se concede
 *
 * `arquivo-local` — ler um arquivo do disco por caminho — **nunca** é dado em
 * pareamento, mesmo quando pedido. Cliente externo manda o conteúdo; quem lê o
 * disco continua sendo só esta janela. É a resposta direta ao fato de que
 * `127.0.0.1` não protege nada: qualquer página aberta no navegador alcança
 * portas locais.
 */

function tempoRelativo(epochSegundos: number | null): string {
  if (!epochSegundos) return "nunca usada";
  const segundos = Math.floor(Date.now() / 1000 - epochSegundos);
  if (segundos < 60) return "agora há pouco";
  if (segundos < 3600) return `há ${Math.floor(segundos / 60)} min`;
  if (segundos < 86400) return `há ${Math.floor(segundos / 3600)} h`;
  return `há ${Math.floor(segundos / 86400)} d`;
}

interface ConexoesProps {
  /** `127.0.0.1:8123` — a porta é dinâmica, então precisa vir de fora. */
  enderecoApi: string;
  motorPronto: boolean;
  avisar: (mensagem: string, tipo?: "sucesso" | "erro") => void;
  /** Lista mantida pelo App, que também a usa no rodapé do trilho. */
  clientes: ClientePareado[];
  aoRecarregar: () => void;
  revogarCliente: (id: string) => Promise<void>;
}

export function Conexoes({
  enderecoApi,
  motorPronto,
  avisar,
  clientes,
  aoRecarregar,
  revogarCliente,
}: ConexoesProps) {
  const [aRevogar, setARevogar] = useState<ClientePareado | null>(null);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-3xl space-y-gutter-lg p-gutter-xl">
        {/* O endereço da API, à vista, no cabeçalho.
            A porta é **dinâmica** (a primeira livre a partir de 8123), então
            sem mostrá-la aqui nem o operador nem quem for escrever uma extensão
            tem como descobrir onde o motor está. É a informação mais importante
            desta tela. */}
        <CabecalhoDeTela
          titulo="Conexões"
          sobrelinha={
            <span className="font-mono text-mono-tag tracking-wider text-outline uppercase">
              API local · 127.0.0.1 · nunca exposta na rede
            </span>
          }
          subtitulo="Quem, além desta janela, alcança o motor desta máquina."
          acoes={
            <>
              <Selo tom={motorPronto ? "deferido" : "neutro"} comPonto>
                API local · {motorPronto ? "ligada" : "subindo"}
              </Selo>
              <button
                onClick={() => {
                  navigator.clipboard?.writeText(enderecoApi);
                  avisar(`${enderecoApi} copiado.`);
                }}
                title="Copiar o endereço"
                className="rounded-sm bg-surface-container-low px-2.5 py-1 font-mono text-mono-code text-primary transition-colors duration-[120ms] hover:bg-surface-container"
              >
                {enderecoApi}
              </button>
            </>
          }
        />

        <Cartao
          titulo="Como um programa se conecta"
          icone="sync_alt"
          descricao="O mesmo caminho vale para a linha de comando, uma extensão de navegador ou um agente."
        >
          <ol className="space-y-gutter-sm font-body text-body-md text-on-surface-variant">
            <li className="flex gap-2.5">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-container font-mono text-mono-tag text-primary">1</span>
              <span>
                O programa chama{" "}
                <code className="rounded bg-surface-container-low px-1 py-0.5 font-mono text-mono-tag text-on-surface">
                  POST /v1/parear
                </code>{" "}
                e recebe um código de seis letras.
              </span>
            </li>
            <li className="flex gap-2.5">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-container font-mono text-mono-tag text-primary">2</span>
              <span>
                O <strong className="text-on-surface">mesmo código</strong> aparece
                aqui numa janela, com o nome de quem pediu. Conferir os dois é o
                que impede aprovar às cegas.
              </span>
            </li>
            <li className="flex gap-2.5">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-container font-mono text-mono-tag text-primary">3</span>
              <span>
                Aprovado, ele recebe uma credencial e passa a aparecer na lista
                abaixo — onde pode ser revogado a qualquer momento.
              </span>
            </li>
          </ol>
          <p className="mt-gutter-md font-body text-body-sm text-on-surface-variant">
            Para a linha de comando, o comando é{" "}
            <code className="rounded bg-surface-container-low px-1 py-0.5 font-mono text-mono-tag text-on-surface">
              tecjustica-sigilo conectar
            </code>
            . O contrato completo para quem escreve um cliente está em{" "}
            <code className="font-mono text-mono-tag">docs/api-local.md</code>.
          </p>
        </Cartao>

        <InstaladorCli avisar={avisar} />

        <Cartao
          titulo="Clientes pareados"
          icone="link"
          descricao="Programas autorizados a usar o motor desta máquina."
        >
          {clientes.length === 0 ? (
            <p className="text-body-md text-on-surface-variant">
              Nenhum cliente pareado. Um programa que peça acesso aparece aqui
              para você aprovar, com um código que precisa bater com o dele.
            </p>
          ) : (
            <ul className="divide-y divide-surface-container">
              {clientes.map((c) => (
                <li
                  key={c.id}
                  className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0"
                >
                  <div className="min-w-0">
                    <p className="text-body-md text-on-surface">{c.nome}</p>
                    <p className="mt-0.5 truncate font-mono text-mono-tag text-outline">
                      {c.origem ?? "origem desconhecida"} ·{" "}
                      {tempoRelativo(c.ultimo_uso)}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {c.escopos.map((e) => (
                        <Selo key={e} tom="acao">
                          {e}
                        </Selo>
                      ))}
                    </div>
                  </div>
                  <Botao
                    tipo="perigo"
                    tamanho="mini"
                    onClick={() => setARevogar(c)}
                  >
                    Revogar
                  </Botao>
                </li>
              ))}
            </ul>
          )}
        </Cartao>

        <Cartao titulo="O que um cliente externo pode fazer"
          icone="policy">
          <ul className="space-y-2 text-body-md text-on-surface-variant">
            <li className="flex gap-2">
              <Selo tom="acao">anonimizar</Selo>
              <span>manda um texto, recebe o texto mascarado.</span>
            </li>
            <li className="flex gap-2">
              <Selo tom="acao">ocr</Selo>
              <span>manda uma imagem, recebe o texto reconhecido.</span>
            </li>
            <li className="flex gap-2">
              <Selo tom="acao">documento</Selo>
              <span>envia um PDF ou DOCX e recebe o texto.</span>
            </li>
          </ul>
          <p className="mt-3 border-l-2 border-tertiary pl-3 text-body-sm leading-normal text-on-surface-variant">
            Ler um arquivo do disco <strong>por caminho</strong> não está nessa
            lista e nunca é concedido. Um cliente externo sempre manda o
            conteúdo; quem abre arquivo do seu computador continua sendo só esta
            janela.
          </p>
        </Cartao>

        <Dialogo
          aberto={aRevogar !== null}
          aoFechar={() => setARevogar(null)}
          titulo="Revogar acesso"
          acoes={
            <>
              <Botao tipo="secundario" onClick={() => setARevogar(null)}>
                Cancelar
              </Botao>
              <Botao
                tipo="perigo"
                onClick={async () => {
                  if (!aRevogar) return;
                  try {
                    await revogarCliente(aRevogar.id);
                    avisar(`${aRevogar.nome} não tem mais acesso.`);
                    aoRecarregar();
                  } catch (erro) {
                    avisar(
                      erro instanceof Error ? erro.message : "Falhou",
                      "erro"
                    );
                  } finally {
                    setARevogar(null);
                  }
                }}
              >
                Revogar
              </Botao>
            </>
          }
        >
          <p>
            <strong className="text-on-surface">{aRevogar?.nome}</strong> perde o
            acesso imediatamente. Para voltar a usar, terá de parear de novo.
          </p>
        </Dialogo>
      </div>
    </div>
  );
}
