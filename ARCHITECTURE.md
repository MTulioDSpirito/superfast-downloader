# Arquitetura — SuperFast DM

## Visão geral
O app é composto por um **servidor local** (UI + API), um **motor de download** multi-conexão, uma **camada de persistência** (SQLite) e uma **extensão de navegador**. Tudo em Python 3 stdlib.

```
┌─────────────┐  web  ┌─────────────────────────────────────────────┐
│ Navegador   │◄─────►│ Servidor local (127.0.0.1:7860)             │
│ (UI + ext.) │  JSON │  ├─ Handler (UI estática + API REST)        │
└─────────────┘       │  └─ Downloader (scheduler + supervisores)   │
      │               │       └─ Task ── thread segmento (Range)    │
      │ POST          │       └─ Task ── thread segmento (Range)    │
      │ /api/add      │       └─ ...                                │
      ▼               └─────────────────────────────────────────────┘
   (link)
```

## Componentes

### `server.py` — servidor local
- `ThreadingHTTPServer` em loopback (`127.0.0.1`) — por padrão **não expõe na rede**.
- Serve a UI estática (`static/`) e uma API REST mínima.
- CORS liberado para a extensão de navegador (mesmo host).
- Opcionalmente abre o navegador (`SFD_OPEN=1`) quando o `/health` responde.

### `engine.py` — motor de download
- **`Task`**: estado por download — segmentos `[start, end, next]`, progresso, velocidade, arquivo e locks. `end=None` representa tamanho desconhecido.
- **`Downloader`**: orquestra as tarefas.
  - **Scheduler** (thread): promove tarefas `pending` enquanto `ativos < SFD_MAX_PARALLEL`.
  - **Supervisor** (1 thread por tarefa ativa): prepara (probe + plano + arquivo) e mantém os segmentos ativos.
  - **Segment thread** (1 por segmento): baixa via `Range`, escreve em offset único e persiste o `next` (com throttle).
- **Multi-conexão**: arquivo pré-alocado; cada segmento escreve em offsets disjuntos, serializados por um lock de arquivo → sem corrupção.
- **Retomada**: o `next` de cada segmento vive no SQLite; ao reiniciar, `_restore()` recarrega as tarefas e o scheduler retoma pelos offsets (inclusive tamanho desconhecido, via `Range: bytes=<n>-`).
- **Erros**: retry com backoff por segmento; erros 4xx permanentes falham rápido; tarefa sem progresso vira `error` (com "Retentar").
- **Velocidade/ETA**: medidor central (Δdone/Δt).

### `db.py` — persistência (SQLite)
- **1 conexão compartilhada** (`check_same_thread=False`) protegida por um `RLock` por instância + commit por escrita — evita deadlock de lock de escrita entre threads (medidor, supervisor e API compartilham a mesma conexão).
- Tabelas: `downloads` (1 linha por tarefa), `segments` (offsets p/ retomada), `config` (key/value).

### `static/` — UI web
- HTML/CSS/JS puros (sem framework), tema escuro.
- Polling de `/api/tasks` a cada 500 ms; barra de progresso, tamanho, velocidade, ETA, status e ações.
- Tamanho desconhecido: barra indeterminada + bytes baixados.

### `extension/` — navegador (MV3)
- `background.js` (service worker) recebe a URL da content script e faz `POST /api/add`.
- `content.js` injeta um botão "SFD" no hover sobre links `<a>`.
- Sem permissões além do host local (loopback).

## Fluxo de um download
1. `POST /api/add` → cria `Task` `pending` (SQLite + memória).
2. Scheduler a promove a `downloading` e lança o supervisor.
3. Supervisor faz **probe** (`Range: bytes=0-0`) → total + `Accept-Ranges` + `Content-Disposition`.
4. Divide em N segmentos (se `Accept-Ranges`) ou usa 1 stream; pré-aloca o arquivo (quando o tamanho é conhecido).
5. Cada segmento baixa seu trecho (`Range`), escreve em offset único e atualiza `done` + persiste `next`.
6. Ao concluir: `completed`. Pausa/retomada/cancel operam por flags + persistência.

## Decisões de projeto
- **stdlib apenas** → portabilidade e zero dependências.
- **loopback por padrão** → superfície de ataque mínima; a extensão usa o mesmo host.
- **1 conexão SQLite** → evita disputa de lock de escrita entre threads.
- **arquivo "r+b" pré-alocado + lock** → escrita multi-offset correta (`"a+b"` ignora `seek()`).
- **`flush()` por chunk** → garante o byte na page cache antes de o offset avançar (integridade na retomada após crash).
