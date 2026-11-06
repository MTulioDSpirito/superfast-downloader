"""engine.py — motor de download multi-conexão (stdlib).

Modelo:
  • 1 supervisor por tarefa (thread).
  • N segmentos por tarefa; 1 thread por segmento ativo (conexão HTTP via Range).
  • Escrita em offset único (arquivo pré-alocado) com lock.
  • Pausa/retomada: o supervisor relança as threads dos segmentos ainda ativos.
  • Velocidade: medidor central (Δdone/Δt) por tarefa.
  • Estado persistido em SQLite (segments.next) para retomada após restart.
  • Tamanho desconhecido (sem Content-Length / chunked): 1 conexão, leitura até
    EOF, retomada via Range "bytes=<cursor>-" (end=None no segmento).
"""
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

UA = "SuperFastDM/1.0 (local download manager)"
CHUNK = 64 * 1024          # 64 KB por leitura
RETRY = 4                  # tentativas por segmento
RETRY_WAIT = 1.5           # espera entre tentativas
METER_INTERVAL = 0.5       # s


class Task:
    def __init__(self, tid, url, filename, path, connections, db):
        self.id = tid
        self.url = url
        self.filename = filename
        self.path = path
        self.connections = connections
        self.db = db
        self.status = "pending"
        self.total = 0
        self.done = 0
        self.speed = 0.0
        self.error = None
        self.eof = False    # tamanho desconhecido: atingiu o fim do stream
        # segmentos: lista de [start, end, next]; end=None => tamanho desconhecido
        self.segments = []
        self._lock = threading.RLock()
        self._file = None
        self._file_lock = threading.Lock()
        self._sup = None
        self._tick_bytes = 0
        self._tick_time = time.time()

    def recompute_done(self):
        with self._lock:
            self.done = sum(max(0, n - s) for (s, e, n) in self.segments)

    def active_segments(self):
        out = []
        for (i, (s, e, n)) in enumerate(self.segments):
            if e is None:
                if not self.eof:
                    out.append((i, s, e, n))
            elif n < e:
                out.append((i, s, e, n))
        return out

    def all_done(self):
        for (s, e, n) in self.segments:
            if e is None:
                if not self.eof:
                    return False
            elif n < e:
                return False
        return True


class Downloader:
    def __init__(self, db, dest_dir, max_parallel=3):
        self.db = db
        self.dest_dir = dest_dir
        os.makedirs(dest_dir, exist_ok=True)
        self.tasks = {}
        self._lock = threading.RLock()
        self._active = 0
        self._cv = threading.Condition(self._lock)
        self.max_parallel = max_parallel
        self._stop = threading.Event()
        self._restore()  # carrega tarefas pendentes do SQLite ANTES dos threads
        threading.Thread(target=self._scheduler, daemon=True).start()
        threading.Thread(target=self._meter, daemon=True).start()

    def _segs_from_db(self, rows):
        """Decodifica segmentos vindos do SQLite (end=-1 => None/desconhecido)."""
        return [[s, (None if e == -1 else e), n] for (_i, s, e, n) in rows]

    def _restore(self):
        """Recarrega tarefas não-finalizadas do SQLite e as retoma (exceto pausadas).
        Tarefas 'downloading'/'pending'/'error' voltam como 'pending' (o scheduler
        pega e retoma pelos segmentos persistidos). 'paused' permanece pausada."""
        for row in self.db.get_tasks():
            st = row.get("status")
            if st in ("completed", "cancelled"):
                continue
            t = Task(row["id"], row["url"], row.get("filename"), row.get("path"),
                     row.get("connections") or 8, self.db)
            t.total = row.get("total") or 0
            t.done = row.get("done") or 0
            t.error = row.get("error")
            t.segments = self._segs_from_db(self.db.get_segments(row["id"]))
            t.recompute_done()
            t.status = "paused" if st == "paused" else "pending"
            with self._lock:
                self.tasks[row["id"]] = t

    # ---------------- API pública ----------------
    def add(self, url, filename=None, connections=8):
        if not filename:
            filename = self._guess_filename(url)
        path = os.path.join(self.dest_dir, filename)
        # evita colisão de nome
        path = self._unique_path(path)
        now = time.time()
        tid = self.db.add_download(url, filename, path, connections, now)
        with self._lock:
            t = Task(tid, url, filename, path, connections, self.db)
            self.tasks[tid] = t
            self._cv.notify_all()
        return tid

    def pause(self, tid):
        t = self.tasks.get(tid)
        if t:
            t.status = "paused"
            self.db.set_status(tid, "paused")

    def resume(self, tid):
        t = self.tasks.get(tid)
        if not t or t.status not in ("paused", "error"):
            return
        if t.status == "error":
            t.error = None
        t.status = "downloading"
        self.db.set_status(tid, "downloading")
        # se o supervisor morreu (erro), relança; pausado: ele já está vivo e pega o flag
        if not (t._sup is not None and t._sup.is_alive()):
            th = threading.Thread(target=self._supervisor, args=(t,), daemon=True)
            t._sup = th
            th.start()

    def cancel(self, tid):
        t = self.tasks.get(tid)
        if t:
            t.status = "cancelled"
            self.db.set_status(tid, "cancelled")

    def remove(self, tid):
        self.cancel(tid)
        with self._lock:
            self.tasks.pop(tid, None)

    def snapshot(self):
        """Retorna lista de dicts p/ a API (unifica mem + db)."""
        out = []
        with self._lock:
            for tid, t in self.tasks.items():
                out.append(self._view(t))
        # tarefas persistidas mas não em memória (depois de restart)
        known = {v["id"] for v in out}
        for row in self.db.get_tasks():
            if row["id"] not in known and row["status"] not in ("cancelled",):
                out.append(row)
        return sorted(out, key=lambda x: x["id"], reverse=True)

    # ---------------- scheduler ----------------
    def _scheduler(self):
        while not self._stop.is_set():
            time.sleep(0.2)
            launched = None
            with self._cv:
                if self._active < self.max_parallel:
                    t = self._next_pending()
                    if t is not None:
                        t.status = "downloading"
                        self.db.set_status(t.id, "downloading")
                        self._active += 1
                        launched = t
            if launched is not None:
                threading.Thread(target=self._supervisor,
                                 args=(launched,), daemon=True).start()

    def _next_pending(self):
        # requer self._lock
        cands = [t for t in self.tasks.values() if t.status == "pending"]
        cands.sort(key=lambda x: x.id)
        return cands[0] if cands else None

    # ---------------- supervisor ----------------
    def _supervisor(self, t):
        t._sup = threading.current_thread()
        try:
            self._prepare(t)
            last_done = t.done
            stuck = 0
            stop_reason = None
            while not self._stop.is_set():
                if t.status == "cancelled":
                    break
                if t.status == "paused":
                    time.sleep(0.2)
                    continue
                if t.all_done():
                    break
                self._launch_segments(t)
                if t.all_done():
                    break
                # sem progresso (ex.: URL inválida/404): para de insistir e vira erro
                if t.done > last_done:
                    last_done = t.done
                    stuck = 0
                else:
                    stuck += 1
                    if stuck >= 3:
                        stop_reason = "stuck"
                        break
                time.sleep(0.05)
            # finaliza
            with t._file_lock:
                if t._file:
                    t._file.close()
                    t._file = None
            if t.status == "cancelled":
                pass
            elif t.all_done():
                t.status = "completed"
                self.db.set_status(t.id, "completed", finished=time.time())
            elif stop_reason == "stuck":
                t.status = "error"
                self.db.set_status(t.id, "error", error=t.error)
            else:
                # shutdown gracioso: persiste o estado atual (retomável) sem marcar erro
                self.db.set_status(t.id, t.status, error=t.error)
        except Exception as e:
            t.status = "error"
            t.error = str(e)
            self.db.set_status(t.id, "error", error=str(e))
        finally:
            with self._cv:
                self._active = max(0, self._active - 1)
                self._cv.notify_all()

    def _prepare(self, t):
        # probe + plano + arquivo (tolera retomada)
        total, accept, cdname = self._probe(t.url)
        # nome via Content-Disposition (só se o usuário não deu nome e o arquivo
        # ainda não existe — em retomada o arquivo já existe e nada muda)
        if cdname and not os.path.exists(t.path):
            newname = cdname[:200]
            if newname != t.filename:
                t.filename = newname
                t.path = self._unique_path(os.path.join(self.dest_dir, newname))
                self.db.set_task(t.id, filename=t.filename, path=t.path)
        t.total = total
        self.db.set_total(t.id, total)
        existing = self.db.get_segments(t.id)
        if existing:
            # retomada: usa segmentos persistidos
            t.segments = self._segs_from_db(existing)
        elif total and accept and t.connections > 1:
            t.segments = self._split(total, t.connections)
        else:
            # 1 conexão: tamanho conhecido (end=total) ou desconhecido (end=None)
            end = total if total else None
            t.segments = [[0, end, 0]]
        self.db.set_segments(t.id, [(s, e, n) for (s, e, n) in t.segments])
        # pré-aloca arquivo (apenas quando o tamanho é conhecido)
        if total:
            self._ensure_file(t, total)
        t.recompute_done()

    def _ensure_file(self, t, size):
        if t._file is None or t._file.closed:
            if not os.path.exists(t.path):
                open(t.path, "wb").close()  # cria vazio
            f = open(t.path, "r+b")  # r+b: seek funciona p/ escrita
            if size and f.tell() < size:
                f.seek(size - 1)
                f.write(b"\x00")
                f.flush()
            t._file = f

    def _split(self, total, n):
        """Divide [0,total) em n segmentos contíguos; o último leva o resto."""
        n = max(1, min(n, 32))
        size = total // n
        segs = []
        pos = 0
        for i in range(n):
            end = total if i == n - 1 else pos + size
            if end > pos:
                segs.append([pos, end, pos])
            pos = end
        return segs

    def _launch_segments(self, t):
        acts = t.active_segments()
        if not acts:
            return
        with ThreadPoolExecutor(max_workers=len(acts)) as ex:
            futs = [ex.submit(self._dl_segment, t, i, s, e, n)
                    for (i, s, e, n) in acts]
            for f in futs:
                f.result()

    # ---------------- segmento ----------------
    def _dl_segment(self, t, idx, start, end, nxt):
        cursor = nxt
        eof = False
        for attempt in range(RETRY):
            if t.status in ("cancelled",):
                return
            if end is not None and cursor >= end:
                break
            req = Request(t.url, method="GET")
            req.add_header("User-Agent", UA)
            if end is not None:
                req.add_header("Range", "bytes=%d-%d" % (cursor, end - 1))
            elif cursor > 0:
                # tamanho desconhecido, retomando: do cursor até o fim
                req.add_header("Range", "bytes=%d-" % cursor)
            try:
                resp = urlopen(req, timeout=30)
                status = getattr(resp, "status", 200)
                # servidor ignorou o Range (200 inteiro) e já há bytes em disco:
                # pula os iniciais (o stream começa no offset 0 do arquivo)
                if cursor > 0 and status == 200:
                    skip = cursor
                    while skip > 0:
                        b = resp.read(min(CHUNK, skip))
                        if not b:
                            break
                        skip -= len(b)
                while True:
                    if t.status == "cancelled":
                        return
                    if t.status == "paused":
                        break
                    if end is not None and cursor >= end:
                        break
                    want = CHUNK if end is None else min(CHUNK, end - cursor)
                    chunk = resp.read(want)
                    if not chunk:
                        eof = True
                        break
                    self._write_chunk(t, cursor, chunk)
                    cursor += len(chunk)
                    self._update_seg(t, idx, start, cursor)
                resp.close()
                if eof or t.status in ("paused", "cancelled"):
                    break
                if end is not None and cursor >= end:
                    break
            except (HTTPError, URLError, OSError, ValueError) as e:
                t.error = str(e)
                self.db.set_status(t.id, "downloading", error=str(e))
                if t.status == "cancelled":
                    return
                # erro de cliente 4xx (exceto 408/425/429) não melhora com retry: falha logo
                if isinstance(e, HTTPError) and 400 <= e.code < 500 \
                        and e.code not in (408, 425, 429):
                    break
                time.sleep(RETRY_WAIT * (attempt + 1))
        # garante persistência final do cursor / flag de EOF
        with t._lock:
            if eof:
                t.eof = True
        if end is not None and cursor >= end:
            self._update_seg(t, idx, start, end)

    def _write_chunk(self, t, offset, chunk):
        with t._file_lock:
            if t._file is None or t._file.closed:
                self._ensure_file(t, max(t.total, offset + len(chunk)))
            f = t._file
            assert f is not None
            f.seek(offset)
            f.write(chunk)
            f.flush()  # garante que o byte está na page cache ANTES de next avançar

    def _update_seg(self, t, idx, start, nxt):
        with t._lock:
            t.segments[idx][2] = nxt
            t.recompute_done()
            done = t.done
        # persiste com throttle (evita flood de escrita)
        self.db.set_done(t.id, done)
        self.db.set_segment_next(t.id, idx, nxt)

    # ---------------- probe ----------------
    def _probe(self, url):
        """Retorna (total, accept_ranges, cd_filename). Tolerante a falha."""
        req = Request(url, method="GET")
        req.add_header("User-Agent", UA)
        req.add_header("Range", "bytes=0-0")
        try:
            resp = urlopen(req, timeout=20)
            status = getattr(resp, "status", 200)
            cr = resp.headers.get("Content-Range") or ""
            cl = resp.headers.get("Content-Length") or "0"
            cd = self._cd_filename(resp.headers)
            if status == 206 and "/" in cr:
                total = int(cr.split("/")[-1].strip() or 0)
                resp.read(1)  # consome o byte
                resp.close()
                return (total, True, cd)
            # 200: servidor ignorou Range
            total = int(cl) if cl.isdigit() else 0
            resp.close()
            return (total, False, cd)
        except HTTPError as e:
            cd = self._cd_filename(e.headers)
            total = 0
            if e.code == 416:
                cr = e.headers.get("Content-Range") or ""
                if "/" in cr:
                    total = int(cr.split("/")[-1].strip() or 0)
                return (total, True, cd)
            return (0, False, cd)
        except (URLError, OSError, ValueError):
            return (0, False, None)

    @staticmethod
    def _cd_filename(headers):
        """Extrai filename de Content-Disposition (com e sem RFC5987)."""
        if not headers:
            return None
        cd = headers.get("Content-Disposition")
        if not cd:
            return None
        m = re.search(r"filename\*\s*=\s*(?:[A-Za-z0-9_-]*'[^']*')?\"?([^\";]+)",
                      cd, re.I)
        if not m:
            m = re.search(r"filename\s*=\s*\"?([^\";]+)\"?", cd, re.I)
        if not m:
            return None
        name = m.group(1).strip().strip('"').strip()
        # des-codifica percent-encoding simples
        try:
            name = re.sub(r"%([0-9A-Fa-f]{2})",
                          lambda g: chr(int(g.group(1), 16)), name)
        except Exception:
            pass
        name = os.path.basename(name)
        return name or None

    # ---------------- medidor ----------------
    def _meter(self):
        while not self._stop.is_set():
            time.sleep(METER_INTERVAL)
            now = time.time()
            with self._lock:
                active = [t for t in self.tasks.values()
                          if t.status == "downloading"]
            for t in active:
                with t._lock:
                    done = t.done
                    lb, lt = t._tick_bytes, t._tick_time
                    t._tick_bytes, t._tick_time = done, now
                dt = now - lt
                if dt > 0:
                    spd = max(0.0, (done - lb) / dt)
                    t.speed = spd
                    self.db.set_speed(t.id, spd)

    # ---------------- helpers ----------------
    def _guess_filename(self, url):
        from urllib.parse import urlparse, unquote
        p = urlparse(url)
        base = os.path.basename(p.path)
        base = unquote(base) or "download"
        if not base:
            base = "download"
        return base[:200]

    def _unique_path(self, path):
        if not os.path.exists(path):
            return path
        root, ext = os.path.splitext(path)
        i = 1
        while os.path.exists("%s (%d)%s" % (root, i, ext)):
            i += 1
        return "%s (%d)%s" % (root, i, ext)

    def _view(self, t):
        with t._lock:
            total, done, speed = t.total, t.done, t.speed
            status, error = t.status, t.error
            conns = t.connections
        path = t.path
        if total:
            pct = 100.0 * done / total
        else:
            pct = 100.0 if status == "completed" else 0.0
        # ETA só faz sentido quando o tamanho total é conhecido
        eta = (total - done) / speed if (total and speed > 0) else None
        return {
            "id": t.id, "url": t.url, "filename": os.path.basename(path),
            "path": path, "total": total, "done": done, "speed": round(speed, 1),
            "status": status, "error": error, "pct": round(pct, 2),
            "connections": conns,
            "eta": eta,
        }
