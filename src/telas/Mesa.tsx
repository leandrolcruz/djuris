import { useApp } from "../estado/AppEstado";
import { AreaDeSoltar } from "../componentes/AreaDeSoltar";
import { Receita } from "../componentes/Receita";
import { Andamento } from "../componentes/Andamento";
import { Botao, Cartao, CabecalhoDeTela, Icone, Pod, Selo } from "../ui";
import type { FileItem } from "../types";

/**
 * Mesa — a tela onde se anonimiza, e a primeira que se vê.
 *
 * Área de soltar à esquerda, receita à direita, um botão. O caminho normal
 * custa **duas ações**: soltar o arquivo e clicar em anonimizar. Contra os ~17
 * controles que a primeira versão pedia a cada vez, porque nenhuma escolha
 * sobrevivia ao fechamento.
 *
 * O que mudou de fato não foi a quantidade de opções — são as mesmas —, foi
 * quem carrega o custo delas. Antes, todas estavam abertas na tela o tempo
 * todo; agora ficam dentro da frase da receita, e só quem quer mudar alguma
 * paga o clique.
 *
 * Embaixo, os últimos documentos guardados. É o que transforma a Mesa de uma
 * caixa de soltar numa tela inicial: quem abre o aplicativo para continuar o de
 * ontem encontra o de ontem aqui, sem passar por Documentos.
 *
 * ## Os dois pods do topo
 *
 * A referência de desenho põe ali "Isolamento Físico / Rede Offline Pronta" e
 * "Inferência BERT / ~120 pág/minuto". A segunda é um número inventado — a
 * medição real desta máquina deu ~450 páginas por hora, e mesmo essa é de uma
 * máquina só, com um modelo só. Anunciar velocidade que a máquina do usuário
 * não vai entregar é promessa quebrada na primeira execução.
 *
 * No lugar entraram duas afirmações verificáveis: que a anonimização não faz
 * chamada de rede nenhuma, e quantos documentos já estão no cofre.
 */

interface MesaProps {
  aoAnonimizar: () => void;
  aoCancelar: () => void;
  motorPronto: boolean;
  /** Os últimos documentos do cofre, mais recentes primeiro. */
  recentes: EntradaDoCofre[];
  /** Quantos documentos o cofre guarda ao todo. */
  totalNoCofre: number;
  aoAbrirRecente: (item: EntradaDoCofre) => void;
  aoVerTodos: () => void;
}

function dataCurta(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

/** Ícone por natureza da peça, para a lista ganhar relevo sem depender da cor. */
function iconeDaPeca(nome: string) {
  const n = nome.toLowerCase();
  if (n.includes("despacho") || n.includes("decisao") || n.includes("decisão")) return "gavel";
  if (n.includes("audiencia") || n.includes("audiência") || n.includes("ata")) return "record_voice_over";
  if (n.includes("certidao") || n.includes("certidão")) return "verified_user";
  if (n.includes("laudo") || n.includes("pericia") || n.includes("perícia")) return "biotech";
  if (n.includes("sentenca") || n.includes("sentença") || n.includes("acordao")) return "balance";
  return "description";
}

export function Mesa({
  aoAnonimizar,
  aoCancelar,
  motorPronto,
  recentes,
  totalNoCofre,
  aoAbrirRecente,
  aoVerTodos,
}: MesaProps) {
  const { estado, despachar, prefs } = useApp();
  const { fila, progresso } = estado;

  // Enquanto o lote roda, a mesa dá lugar ao andamento.
  if (progresso) {
    return (
      <Andamento
        current={progresso.atual}
        total={progresso.total}
        fileName={progresso.nomeArquivo}
        phase={progresso.etapa}
        onCancelar={aoCancelar}
      />
    );
  }

  const definirArquivos = (arquivos: FileItem[]) =>
    despachar({ tipo: "definir-fila", arquivos });

  const semArquivo = fila.length === 0;
  const semEntidade = prefs.entidades.length === 0;
  const impedido = semArquivo || semEntidade || !motorPronto;

  /* Um botão desabilitado sem motivo é um beco sem saída. O motivo fica
     escrito ao lado dele, não escondido num `title` que só aparece no hover. */
  const motivo = !motorPronto
    ? "O motor de anonimização ainda está subindo."
    : semArquivo
      ? "Solte ao menos um arquivo para começar."
      : semEntidade
        ? "Escolha ao menos um tipo de dado na receita."
        : null;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-[1240px] flex-col gap-gutter-xl p-gutter-xl">
        <CabecalhoDeTela
          grande
          sobrelinha={
            <>
              <Selo tom="deferido" forma="pilula" comPonto>
                MOTOR LOCAL · SEM SAÍDA DE REDE
              </Selo>
              <span className="font-mono text-mono-tag tracking-wider text-outline uppercase">
                LGPD · Res. CNJ 615/2025
              </span>
            </>
          }
          titulo="Anonimizar documentos"
          subtitulo="Solte os autos ou peças em PDF, DOCX, XLSX, TXT ou imagem. A leitura, o reconhecimento de texto e a detecção acontecem inteiros nesta máquina."
          acoes={
            <>
              <Pod
                icone="shield_locked"
                rotulo="Saída de rede"
                valor="nenhuma"
                complemento="ao anonimizar"
                tom="selado"
              />
              <Pod
                icone="encrypted"
                rotulo="No cofre"
                valor={totalNoCofre.toLocaleString("pt-BR")}
                complemento={totalNoCofre === 1 ? "documento" : "documentos"}
              />
            </>
          }
        />

        <div className="grid grid-cols-1 items-start gap-gutter-lg lg:grid-cols-12">
          <div className="lg:col-span-7">
            <AreaDeSoltar fila={fila} aoMudarFila={definirArquivos} />
          </div>

          <div className="flex flex-col gap-gutter-md lg:col-span-5">
            <Cartao
              titulo="Receita de anonimização"
              icone="tune"
              acao={<Selo tom="acao">perfil desta máquina</Selo>}
            >
              <div className="flex flex-col gap-gutter-md">
                <div className="rounded-lg bg-surface-container-low p-gutter-md">
                  <Receita />
                </div>

                <Botao
                  tipo="primario"
                  tamanho="grande"
                  icone="lock_reset"
                  onClick={aoAnonimizar}
                  disabled={impedido}
                  className="w-full"
                >
                  Iniciar anonimização
                  {fila.length > 0 && ` · ${fila.length} peça${fila.length > 1 ? "s" : ""}`}
                </Botao>

                <p
                  className={[
                    "flex items-center justify-center gap-1.5 text-center font-body text-body-sm",
                    motivo ? "text-on-surface-variant" : "text-secondary",
                  ].join(" ")}
                >
                  {!motivo && <Icone nome="verified" tamanho={16} />}
                  {motivo ?? "Tudo pronto. O resultado abre para revisão antes de ser salvo."}
                </p>
              </div>
            </Cartao>
          </div>
        </div>

        {recentes.length > 0 && (
          <section aria-labelledby="recentes-titulo" className="flex flex-col gap-gutter-md">
            <div className="flex items-center justify-between gap-gutter-sm">
              <h2
                id="recentes-titulo"
                className="flex items-center gap-gutter-xs font-display text-headline-lg text-on-surface"
              >
                <span className="text-primary">
                  <Icone nome="history_edu" tamanho={22} />
                </span>
                Guardados recentemente no cofre
              </h2>
              <Botao tipo="discreto" icone="arrow_forward" iconeAoFim onClick={aoVerTodos}>
                Ver o cofre inteiro
              </Botao>
            </div>

            <div className="grid grid-cols-1 gap-gutter-md md:grid-cols-2 xl:grid-cols-3">
              {recentes.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => aoAbrirRecente(item)}
                  className="group flex flex-col justify-between gap-gutter-md rounded-lg bg-surface-container-lowest p-gutter-md text-left shadow-sm transition-all duration-[120ms] hover:shadow-md"
                >
                  <div className="flex flex-col gap-gutter-xs">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="grid size-8 shrink-0 place-items-center rounded-sm bg-surface-container text-primary">
                        <Icone nome={iconeDaPeca(item.nome)} tamanho={18} />
                      </span>
                      <span className="truncate font-mono text-mono-code text-on-surface transition-colors duration-[120ms] group-hover:text-primary">
                        {item.nome}
                      </span>
                    </div>
                    <p className="font-mono text-mono-tag text-on-surface-variant">
                      {item.cnj ?? "peça avulsa"} · {dataCurta(item.gravadoEm)}
                    </p>
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <Selo tom={item.totalOcorrencias > 0 ? "acao" : "neutro"}>
                        {item.totalOcorrencias.toLocaleString("pt-BR")}{" "}
                        {item.totalOcorrencias === 1 ? "ocorrência" : "ocorrências"}
                      </Selo>
                      {item.paginasComErro > 0 && (
                        <Selo tom="perigo">
                          {item.paginasComErro} página{item.paginasComErro > 1 ? "s" : ""} sem OCR
                        </Selo>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2 text-outline">
                    <span className="font-mono text-mono-tag">abrir revisão</span>
                    <Icone nome="arrow_forward" tamanho={16} />
                  </div>
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
