#!/usr/bin/env python3
"""Локальный веб-сайт со списком проектов Jira Server/DC 8.13.20.

Один файл, только стандартная библиотека — ни pip, ни зависимостей.
Сервер отдаёт HTML-страницу и сам ходит в Jira (GET /rest/api/2/project),
чтобы не упереться в CORS и не светить токен в браузере.

Конфиг через переменные окружения:
    JIRA_BASE_URL   https://jira.company.ru   (обязательно, без /rest/...)
    JIRA_TOKEN      <токен>                    (обязательно)
    JIRA_AUTH_MODE  bearer | basic             (по умолчанию bearer)
    JIRA_USERNAME   <логин>                    (нужен только для basic)
    JIRA_INSECURE   1                          (не проверять TLS — корп. self-signed CA)
    JIRA_TIMEOUT    30                         (секунды)
    PORT            8000                        (порт локального сайта)

Запуск:
    python3 server.py
    # открой в браузере http://localhost:8000
"""
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def load_dotenv(path=".env"):
    """Читает .env (KEY=VALUE построчно) в окружение. Без зависимостей.
    Уже заданные переменные окружения не перезатирает."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def cfg():
    base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    token = os.environ.get("JIRA_TOKEN", "").strip()
    auth_mode = os.environ.get("JIRA_AUTH_MODE", "bearer").strip().lower()
    username = os.environ.get("JIRA_USERNAME", "").strip()
    insecure = os.environ.get("JIRA_INSECURE", "").strip() in ("1", "true", "yes")
    timeout = int(os.environ.get("JIRA_TIMEOUT", "30"))
    return base_url, token, auth_mode, username, insecure, timeout


def fetch_projects():
    """Возвращает (projects_list, base_url). Кидает RuntimeError с понятным текстом."""
    base_url, token, auth_mode, username, insecure, timeout = cfg()
    if not base_url:
        raise RuntimeError("Не задан JIRA_BASE_URL")
    if not token:
        raise RuntimeError("Не задан JIRA_TOKEN")
    if auth_mode == "basic" and not username:
        raise RuntimeError("Для JIRA_AUTH_MODE=basic нужен JIRA_USERNAME")

    if auth_mode == "basic":
        raw = f"{username}:{token}".encode("utf-8")
        auth = "Basic " + base64.b64encode(raw).decode("ascii")
    else:  # bearer — режим по умолчанию для токена Kantega SSO
        auth = "Bearer " + token

    req = urllib.request.Request(
        base_url.rstrip("/") + "/rest/api/2/project",
        headers={"Authorization": auth, "Accept": "application/json"},
    )
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        hints = {
            401: " (токен неверен/просрочен либо режим auth не совпадает: bearer vs basic)",
            403: " (токен валиден, но нет прав / CAPTCHA-lock)",
            404: " (проверь JIRA_BASE_URL и контекст-путь)",
        }
        raise RuntimeError(f"Jira вернула {e.code}{hints.get(e.code, '')}. {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Сетевая ошибка: {e.reason}. При self-signed CA попробуй JIRA_INSECURE=1")

    return data, base_url.rstrip("/")


PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Проекты Jira</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
         background: #f5f6f8; color: #1a1a1a; }
  header { background: #0052cc; color: #fff; padding: 16px 24px; }
  header h1 { margin: 0; font-size: 18px; font-weight: 600; }
  .wrap { max-width: 1000px; margin: 24px auto; padding: 0 16px; }
  .bar { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
  input[type=search] { flex: 1; min-width: 200px; padding: 10px 12px; font-size: 14px;
         border: 1px solid #ccc; border-radius: 6px; }
  button { padding: 10px 16px; font-size: 14px; border: 0; border-radius: 6px;
         background: #0052cc; color: #fff; cursor: pointer; }
  button:hover { background: #0043a6; }
  .count { color: #555; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
  th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid #eee; font-size: 14px; }
  th { background: #fafbfc; font-weight: 600; cursor: pointer; user-select: none; }
  tr:hover td { background: #f8f9ff; }
  td.key a { color: #0052cc; text-decoration: none; font-weight: 600; }
  td.key a:hover { text-decoration: underline; }
  .err { background: #ffebe6; border: 1px solid #ff8f73; color: #bf2600;
         padding: 16px; border-radius: 8px; white-space: pre-wrap; }
  .muted { color: #777; }
</style>
</head>
<body>
<header><h1>Проекты Jira</h1></header>
<div class="wrap">
  <div class="bar">
    <input type="search" id="q" placeholder="Фильтр по ключу или названию…" autofocus>
    <button id="reload">Обновить</button>
    <span class="count" id="count"></span>
  </div>
  <div id="out"><p class="muted">Загрузка…</p></div>
</div>
<script>
let rows = [], baseUrl = "";
const out = document.getElementById("out");
const q = document.getElementById("q");
const count = document.getElementById("count");
let sortKey = "key", sortAsc = true;

function esc(s){ return (s||"").replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function render(){
  const term = q.value.trim().toLowerCase();
  let list = rows.filter(r =>
    !term || (r.key||"").toLowerCase().includes(term) || (r.name||"").toLowerCase().includes(term));
  list.sort((a,b) => {
    const x=(a[sortKey]||"").toString().toLowerCase(), y=(b[sortKey]||"").toString().toLowerCase();
    return (x<y?-1:x>y?1:0) * (sortAsc?1:-1);
  });
  count.textContent = list.length + " из " + rows.length;
  if(!list.length){ out.innerHTML = '<p class="muted">Ничего не найдено.</p>'; return; }
  const th = (k,label) => `<th data-k="${k}">${label}${sortKey===k?(sortAsc?" ▲":" ▼"):""}</th>`;
  let html = '<table><thead><tr>' +
    th("key","Ключ") + th("name","Название") + th("lead","Лид") + th("projectTypeKey","Тип") +
    '</tr></thead><tbody>';
  for(const r of list){
    const lead = r.lead ? (r.lead.displayName || r.lead.name || "") : "";
    const link = baseUrl ? baseUrl + "/projects/" + encodeURIComponent(r.key) : "#";
    html += `<tr>
      <td class="key"><a href="${link}" target="_blank" rel="noopener">${esc(r.key)}</a></td>
      <td>${esc(r.name)}</td>
      <td>${esc(lead)}</td>
      <td class="muted">${esc(r.projectTypeKey||"")}</td>
    </tr>`;
  }
  out.innerHTML = html + '</tbody></table>';
  out.querySelectorAll("th").forEach(el => el.onclick = () => {
    const k = el.dataset.k;
    if(sortKey===k) sortAsc=!sortAsc; else { sortKey=k; sortAsc=true; }
    render();
  });
}

async function load(){
  out.innerHTML = '<p class="muted">Загрузка…</p>';
  try {
    const resp = await fetch("/api/projects");
    const data = await resp.json();
    if(!resp.ok){ out.innerHTML = '<div class="err">'+esc(data.error||"Ошибка")+'</div>'; count.textContent=""; return; }
    rows = data.projects || [];
    baseUrl = data.baseUrl || "";
    render();
  } catch(e){
    out.innerHTML = '<div class="err">Не удалось обратиться к серверу: '+esc(e.message)+'</div>';
  }
}

q.addEventListener("input", render);
document.getElementById("reload").addEventListener("click", load);
load();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        payload = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._send(200, PAGE, "text/html")
        elif self.path.startswith("/api/projects"):
            try:
                projects, base_url = fetch_projects()
                self._send(200, json.dumps({"projects": projects, "baseUrl": base_url}), "application/json")
            except RuntimeError as e:
                self._send(502, json.dumps({"error": str(e)}, ensure_ascii=False), "application/json")
        else:
            self._send(404, json.dumps({"error": "not found"}), "application/json")

    def log_message(self, fmt, *a):  # тише в консоли
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % a))


def main():
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))  # .env рядом со скриптом
    port = int(os.environ.get("PORT", "8000"))
    # Ранняя проверка конфигурации, чтобы не поднимать сервер вслепую.
    base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    if not base_url or not os.environ.get("JIRA_TOKEN", "").strip():
        print("⚠  Не заданы JIRA_BASE_URL / JIRA_TOKEN — страница откроется, но покажет ошибку.")
        print("   export JIRA_BASE_URL=... ; export JIRA_TOKEN=...")
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Сайт со списком проектов: http://localhost:{port}  (Ctrl+C для остановки)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")


if __name__ == "__main__":
    main()
