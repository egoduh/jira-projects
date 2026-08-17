# JiraProjects

Получение списка проектов из **Jira Server/DC 8.13.20** через `GET /rest/api/2/project`.

Аутентификация — токен **Kantega SSO Enterprise** (Bearer). Kantega выдаёт персональные
токены поверх Jira 8.13, у которой нет нативных PAT (они появились только в Jira 8.14).

Три способа посмотреть список — выбирай по ситуации:

- **`server.py`** — 🌐 локальный сайт со списком проектов (таблица, поиск, сортировка).
  Только стандартная библиотека Python. **Основной вариант.**
- **`jira_projects.py`** — тот же список в консоли (таблица или `--json`).
- **`.NET 8`** (`*.cs`) — если предпочитаешь основной стек.

---

## 🌐 Сайт (основной вариант)

Нужен только `python3` (обычно уже стоит). Сервер сам ходит в Jira и отдаёт страницу —
это обходит CORS и не светит токен в браузере.

```bash
export JIRA_BASE_URL="https://jira.company.ru"
export JIRA_TOKEN="<токен-из-Kantega>"
python3 server.py
# открой в браузере http://localhost:8000
```

На странице: таблица Ключ / Название / Лид / Тип, живой фильтр по ключу и названию,
сортировка по клику на заголовок, ссылка на каждый проект, кнопка «Обновить».
Порт меняется через `PORT=9000 python3 server.py`.

Режим Basic (если токен Kantega работает как пароль): `JIRA_AUTH_MODE=basic` + `JIRA_USERNAME=<логин>`.
Корп. self-signed CA: `JIRA_INSECURE=1`.

| Переменная       | По умолчанию | Назначение                                   |
|------------------|--------------|----------------------------------------------|
| `JIRA_BASE_URL`  | —            | URL инстанса без `/rest/...`                 |
| `JIRA_TOKEN`     | —            | Токен Kantega (bearer) или пароль (basic)    |
| `JIRA_AUTH_MODE` | `bearer`     | `bearer` или `basic`                         |
| `JIRA_USERNAME`  | —            | Только для `basic`                           |
| `JIRA_INSECURE`  | —            | `1` — не проверять TLS                        |
| `JIRA_TIMEOUT`   | `30`         | Таймаут, сек                                 |
| `PORT`           | `8000`       | Порт локального сайта                        |

---

## Консольный вариант

```bash
python3 jira_projects.py            # таблица KEY / NAME / LEAD
python3 jira_projects.py --json     # сырой JSON
```
Те же переменные окружения, что выше.

| Переменная       | По умолчанию | Назначение                                   |
|------------------|--------------|----------------------------------------------|
| `JIRA_BASE_URL`  | —            | URL инстанса без `/rest/...`                 |
| `JIRA_TOKEN`     | —            | Токен Kantega (bearer) или пароль (basic)    |
| `JIRA_AUTH_MODE` | `bearer`     | `bearer` или `basic`                         |
| `JIRA_USERNAME`  | —            | Только для `basic`                           |
| `JIRA_INSECURE`  | —            | `1` — не проверять TLS                        |
| `JIRA_TIMEOUT`   | `30`         | Таймаут, сек                                 |

---

## .NET 8

## Настройка секретов

Токен и URL не хранятся в git. Задай их одним из способов.

### Вариант 1 — user-secrets (рекомендуется для локали)

```bash
cd ~/AI/jira-projects
dotnet user-secrets set "Jira:BaseUrl" "https://jira.company.ru"
dotnet user-secrets set "Jira:Token"   "<токен-из-Kantega>"
```

### Вариант 2 — переменные окружения

Двойное подчёркивание = вложенность секции:

```bash
export JIRA__BASEURL="https://jira.company.ru"
export JIRA__TOKEN="<токен-из-Kantega>"
```

## Запуск

```bash
dotnet run              # таблица KEY / NAME / LEAD
dotnet run -- --json    # сырой JSON
```

## Параметры (секция Jira)

| Ключ                    | По умолчанию | Назначение                                              |
|-------------------------|--------------|---------------------------------------------------------|
| `BaseUrl`               | —            | Базовый URL инстанса без `/rest/...`                    |
| `AuthMode`              | `Bearer`     | `Bearer` (Kantega токен) или `Basic` (`user:token`)     |
| `Token`                 | —            | Токен Kantega (Bearer) либо пароль/токен (Basic)        |
| `Username`              | —            | Нужен только для `AuthMode=Basic`                       |
| `InsecureSkipTlsVerify` | `false`      | `true` — не проверять TLS (корп. self-signed CA)        |
| `TimeoutSeconds`        | `30`         | Таймаут HTTP                                             |

## Если токен Kantega настроен как Basic

Некоторые инсталляции Kantega отдают токен, который используется как пароль в Basic-auth
(`username:token`). Тогда:

```bash
dotnet user-secrets set "Jira:AuthMode" "Basic"
dotnet user-secrets set "Jira:Username" "<логин>"
dotnet user-secrets set "Jira:Token"    "<токен>"
```

Клиент на 401 подскажет, что режим auth может не совпадать.

## Структура

- `JiraClient.cs` — HTTP-клиент к REST API, обработка ошибок с подсказками по кодам.
- `JiraOptions.cs` — настройки + валидация.
- `Models/JiraProject.cs` — модель проекта.
- `Program.cs` — CLI: конфиг, вывод таблицей или JSON.
