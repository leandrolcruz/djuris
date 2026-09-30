import { contextBridge, ipcRenderer, webUtils } from "electron";

/**
 * O preload roda em SANDBOX, e ali `require` de arquivo do projeto não resolve
 * — o módulo não é encontrado, a exceção derruba o preload inteiro e
 * `window.electronAPI` simplesmente não existe. Nada aparece no terminal: a
 * interface sobe, o cofre fica "indisponível", o backend parece mudo, e nada
 * aponta para aqui. Foi o que aconteceu ao importar `./moldura` daqui.
 *
 * Por isso o que precisa de lógica é calculado no MAIN (que pode importar à
 * vontade) e chega por `additionalArguments`, que o sandbox deixa passar.
 */
function argumentoNumerico(nome: string, padrao: number): number {
  const prefixo = `--${nome}=`;
  const achado = process.argv.find((a) => a.startsWith(prefixo));
  if (achado === undefined) return padrao;
  const valor = Number(achado.slice(prefixo.length));
  return Number.isFinite(valor) ? valor : padrao;
}

contextBridge.exposeInMainWorld("electronAPI", {
  getBackendPort: (): Promise<number> => ipcRenderer.invoke("get-backend-port"),
  getBackendToken: (): Promise<string> => ipcRenderer.invoke("get-backend-token"),
  janela: {
    /** Cor da barra de título nativa, para acompanhar o tema da interface. */
    pintarBarra: (cores: { fundo: string; simbolo: string }): Promise<void> =>
      ipcRenderer.invoke("barra-de-titulo", cores),
    /**
     * Quanto o conteúdo precisa recuar à esquerda para não ficar sob os botões
     * da janela. No macOS os três semáforos ficam nesse canto, que é onde a
     * barra lateral põe a marca; nas outras plataformas é zero.
     *
     * Vai calculado daqui, e não como o nome da plataforma: o renderer não tem
     * por que aprender a regra de cada sistema, e um `if (mac)` espalhado pela
     * interface é como a regra começa a divergir de si mesma.
     */
    recuoDosSemaforos: argumentoNumerico("recuo-semaforos", 0),
  },
  /** Caminho absoluto de um File vindo de drag-and-drop ou <input type="file">. */
  getPathForFile: (file: File): string => {
    try {
      return webUtils.getPathForFile(file);
    } catch {
      return "";
    }
  },
  readFile: (path: string) => ipcRenderer.invoke("read-file", path),
  saveFile: (path: string, content: string) =>
    ipcRenderer.invoke("save-file", path, content),
  saveFileBinary: (path: string, base64: string) =>
    ipcRenderer.invoke("save-file-binary", path, base64),
  selectFiles: () => ipcRenderer.invoke("select-files"),
  selectDirectory: () => ipcRenderer.invoke("select-directory"),
  cofre: {
    disponivel: () => ipcRenderer.invoke("cofre-disponivel"),
    listar: () => ipcRenderer.invoke("cofre-listar"),
    gravar: (entrada: unknown, conteudo: unknown) =>
      ipcRenderer.invoke("cofre-gravar", entrada, conteudo),
    atualizar: (id: string, entrada: unknown, conteudo: unknown) =>
      ipcRenderer.invoke("cofre-atualizar", id, entrada, conteudo),
    marcarRevisado: (id: string) => ipcRenderer.invoke("cofre-marcar-revisado", id),
    ler: (id: string) => ipcRenderer.invoke("cofre-ler", id),
    apagar: (id: string) => ipcRenderer.invoke("cofre-apagar", id),
    esvaziar: () => ipcRenderer.invoke("cofre-esvaziar"),
    expurgar: (dias: number) => ipcRenderer.invoke("cofre-expurgar", dias),
  },
  /* A chave da API não tem canal de leitura, e isso é proposital: o processo
     principal a usa ao montar a requisição, e o renderer só precisa saber se
     ela existe. `ultimos4` basta para reconhecer qual chave está guardada. */
  segredo: {
    resumo: () => ipcRenderer.invoke("segredo-resumo"),
    guardar: (chave: string) => ipcRenderer.invoke("segredo-guardar", chave),
    apagar: () => ipcRenderer.invoke("segredo-apagar"),
  },
  /* `abrir` recebe ids do cofre, nunca texto: não há como o renderer mandar
     conteúdo arbitrário para a nuvem, porque o canal não aceita conteúdo. */
  chat: {
    modelos: () => ipcRenderer.invoke("chat-modelos"),
    abrir: (ids: string[], modelo?: string) =>
      ipcRenderer.invoke("chat-abrir", ids, modelo),
    listar: () => ipcRenderer.invoke("chat-listar"),
    renomear: (id: string, titulo: string) =>
      ipcRenderer.invoke("chat-renomear", id, titulo),
    estado: (id: string) => ipcRenderer.invoke("chat-estado", id),
    orcamento: (id: string) => ipcRenderer.invoke("chat-orcamento", id),
    previsualizar: (id: string) => ipcRenderer.invoke("chat-previsualizar", id),
    perguntar: (id: string, pergunta: string) =>
      ipcRenderer.invoke("chat-perguntar", id, pergunta),
    cancelar: (id: string) => ipcRenderer.invoke("chat-cancelar", id),
    fechar: (id: string) => ipcRenderer.invoke("chat-fechar", id),
    sondar: (modelo: string) => ipcRenderer.invoke("chat-sondar", modelo),
  },
  cli: {
    status: () => ipcRenderer.invoke("cli-status"),
    installWindows: () => ipcRenderer.invoke("cli-install-windows"),
    uninstallWindows: () => ipcRenderer.invoke("cli-uninstall-windows"),
    installWsl: () => ipcRenderer.invoke("cli-install-wsl"),
    uninstallWsl: () => ipcRenderer.invoke("cli-uninstall-wsl"),
  },
});
