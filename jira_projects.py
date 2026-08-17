#!/usr/bin/env python3
"""Список проектов из Jira Server/DC 8.13.20 через GET /rest/api/2/project.

Только стандартная библиотека — ни pip, ни requests не нужны.
Аутентификация: Bearer (токен Kantega SSO Enterprise) либо Basic (user:token).

Конфиг через переменные окружения:
    JIRA_BASE_URL   https://jira.company.ru   (обязательно, без /rest/...)
    JIRA_TOKEN      <токен>                    (обязательно)
    JIRA_AUTH_MODE  bearer | basic             (по умолчанию bearer)
    JIRA_USERNAME   <логин>                    (нужен только для basic)
    JIRA_INSECURE   1                          (не проверять TLS — корп. self-signed CA)
    JIRA_TIMEOUT    30                         (секунды)

Запуск:
    python3 jira_projects.py            # таблица KEY / NAME / LEAD
    python3 jira_projects.py --json     # сырой JSON
"""
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request


def build_request(base_url, token, auth_mode, username):
    url = base_url.rstrip("/") + "/rest/api/2/project"
    if auth_mode == "basic":
        raw = f"{username}:{token}".encode("utf-8")
        auth = "Basic " + base64.b64encode(raw).decode("ascii")
    else:  # bearer — режим по умолчанию для токена Kantega
        auth = "Bearer " + token
    return urllib.request.Request(
        url,
        headers={"Authorization": auth, "Accept": "application/json"},
    )


def fetch_projects(req, timeout, insecure):
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    token = os.environ.get("JIRA_TOKEN", "").strip()
    auth_mode = os.environ.get("JIRA_AUTH_MODE", "bearer").strip().lower()
    username = os.environ.get("JIRA_USERNAME", "").strip()
    insecure = os.environ.get("JIRA_INSECURE", "").strip() in ("1", "true", "yes")
    timeout = int(os.environ.get("JIRA_TIMEOUT", "30"))

    if not base_url:
        sys.exit("Ошибка: не задан JIRA_BASE_URL")
    if not token:
        sys.exit("Ошибка: не задан JIRA_TOKEN")
    if auth_mode == "basic" and not username:
        sys.exit("Ошибка: для JIRA_AUTH_MODE=basic нужен JIRA_USERNAME")

    req = build_request(base_url, token, auth_mode, username)
    try:
        projects = fetch_projects(req, timeout, insecure)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        hints = {
            401: " (токен неверен/просрочен либо режим auth не совпадает: bearer vs basic)",
            403: " (токен валиден, но нет прав / сработал CAPTCHA-lock)",
            404: " (проверь JIRA_BASE_URL и контекст-путь инстанса)",
        }
        sys.exit(f"Jira вернула {e.code}{hints.get(e.code, '')}. Тело: {body}")
    except urllib.error.URLError as e:
        sys.exit(f"Сетевая ошибка: {e.reason}. При self-signed CA попробуй JIRA_INSECURE=1")

    if "--json" in sys.argv:
        print(json.dumps(projects, ensure_ascii=False, indent=2))
        return

    print(f"Проектов: {len(projects)}\n")
    print(f"{'KEY':<12} {'NAME':<40} LEAD")
    print("-" * 74)
    for p in sorted(projects, key=lambda x: x.get("key", "")):
        lead = p.get("lead") or {}
        lead_name = lead.get("displayName") or lead.get("name") or ""
        name = p.get("name", "")
        if len(name) > 40:
            name = name[:39] + "…"
        print(f"{p.get('key', ''):<12} {name:<40} {lead_name}")


if __name__ == "__main__":
    main()
