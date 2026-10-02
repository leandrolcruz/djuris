@echo off
REM Wrapper que chama o Python embutido do instalador com cli.py.
REM
REM O `%*` repassa a linha de comando inteira, então os subcomandos funcionam
REM sem que este arquivo precise conhecê-los:
REM
REM   djuris.cmd autos.pdf              (PDF, DOCX, imagem — com OCR)
REM   djuris.cmd arquivo.txt -o saida.md
REM   type arquivo.txt | djuris.cmd
REM   djuris.cmd ler autos.pdf          (extrai sem anonimizar)
REM   djuris.cmd ocr pagina.png
REM   djuris.cmd reidratar resposta.txt --autos 5626981
REM   djuris.cmd status                 (app no ar? em que modo?)
REM   djuris.cmd conectar               (autoriza esta CLI)
REM   djuris.cmd mcp                    (servidor MCP em stdio)
REM   djuris.cmd --help
REM
REM Onde encontrar este .cmd depois de instalar o app:
REM   %LOCALAPPDATA%\Programs\Direito&Juris\resources\python-backend\djuris.cmd
REM
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%python-embed\python.exe"
set "CLI=%ROOT%cli.py"
"%PYTHON%" "%CLI%" %*
endlocal
