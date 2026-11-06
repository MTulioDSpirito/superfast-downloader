# Instalador — Windows (SuperFast DM)

Este diretório contém os insumos para gerar o instalador do Windows.

## Gerar o instalador `.exe`
1. Instale o **Inno Setup 6** — https://jrsoftware.org/isinfo.php
2. Abra `superfastdm.iss` no Inno Setup.
3. **File → Compile** (ou Ctrl+F9).
4. O instalador sai em `output\SuperFastDM-Setup.exe`.

O `.ico` já está incluído (`superfastdm.ico`). Para regenerá-lo:
```
python gen_ico.py superfastdm.ico
```

## O que o instalador faz
- Instala o app em `C:\Program Files\SuperFastDM\` (ou por usuário, sem admin).
- Cria atalhos no Menu Iniciar e (opcional) no desktop.
- Opcionalmente inicia o app ao final (janela do launcher + abre o navegador).

## Modo portátil (sem instalador)
Dê dois cliques em `SuperFastDM.bat`:
- No **instalador** (pasta de instalação), ele encontra o `server.py` na mesma pasta.
- No **repositório** (esta pasta), ele usa `..\..\app\server.py`.

Para encerrar: feche a janela do launcher, ou rode `stop-superfastdm.bat`.

## Requisitos
- **Python 3** no PATH (marque "Add python.exe to PATH" na instalação).
- Windows 10/11 (o `curl` embutido é usado no launcher).
