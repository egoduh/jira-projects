namespace JiraProjects;

public enum JiraAuthMode
{
    /// <summary>Authorization: Bearer &lt;token&gt; — режим по умолчанию для токена Kantega SSO Enterprise.</summary>
    Bearer,

    /// <summary>Authorization: Basic base64(user:token|password) — если инстанс настроен на basic.</summary>
    Basic
}

/// <summary>Настройки подключения к Jira. Секреты сюда приходят из user-secrets / env, не из appsettings в git.</summary>
public sealed class JiraOptions
{
    /// <summary>Базовый URL инстанса, напр. https://jira.company.ru (без /rest/...).</summary>
    public string BaseUrl { get; set; } = "";

    public JiraAuthMode AuthMode { get; set; } = JiraAuthMode.Bearer;

    /// <summary>Токен Kantega SSO для Bearer, либо пароль/токен для Basic.</summary>
    public string Token { get; set; } = "";

    /// <summary>Имя пользователя — нужно только для AuthMode=Basic.</summary>
    public string? Username { get; set; }

    /// <summary>Игнорировать ошибки TLS-сертификата (self-signed корп. CA). По умолчанию false.</summary>
    public bool InsecureSkipTlsVerify { get; set; }

    public int TimeoutSeconds { get; set; } = 30;

    public void Validate()
    {
        if (string.IsNullOrWhiteSpace(BaseUrl))
            throw new InvalidOperationException("Jira:BaseUrl не задан. См. README (user-secrets или env JIRA__BASEURL).");
        if (string.IsNullOrWhiteSpace(Token))
            throw new InvalidOperationException("Jira:Token не задан. Задай через user-secrets или env JIRA__TOKEN.");
        if (AuthMode == JiraAuthMode.Basic && string.IsNullOrWhiteSpace(Username))
            throw new InvalidOperationException("Для AuthMode=Basic нужен Jira:Username.");
    }
}
