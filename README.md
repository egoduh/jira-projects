# JiraProjects

Мини-сервис на .NET 8 для получения списка проектов из **Jira Server/DC 8.13.20**
через `GET /rest/api/2/project`.

Аутентификация — токен **Kantega SSO Enterprise** (Bearer). Kantega выдаёт персональные
токены поверх Jira 8.13, у которой нет нативных PAT (они появились только в Jira 8.14).

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
