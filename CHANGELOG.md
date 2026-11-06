# Changelog

## 1.1 — 2026-11-05
- **Correção**: downloads com **tamanho desconhecido** (sem `Content-Length`/chunked) — antes geravam arquivo de 0 bytes marcado como "concluído"; agora baixam até o EOF, com retomada.
- **Melhoria**: erros HTTP permanentes (4xx) falham rápido (sem retry infinito); tarefa sem progresso vira `error` e permite "Retentar".
- **Melhoria**: nome do arquivo via `Content-Disposition` quando o usuário não especifica.
- **Melhoria**: pasta de dados dedicada (`~/.superfast-dm`) para o banco, fácil de limpar ao desinstalar.
- **Melhoria**: opção `SFD_OPEN=1` abre o navegador automaticamente.
- **Melhoria**: UI trata tamanho desconhecido (barra indeterminada + bytes baixados).
- **Novo**: instaladores macOS (`.app`/`.dmg`) e Windows (Inno Setup).
- **Validado**: retomada após reinício do servidor (persistência em SQLite, integridade byte a byte).

## 1.0 — 2026-11-04
- MVP: servidor local (UI + API), motor multi-conexão via `Range`, pausa/retomada, fila, histórico em SQLite, UI web, extensão de navegador (MV3).
- Validação: download byte-idêntico (sha256), pausa congela o progresso, retomada íntegra.
