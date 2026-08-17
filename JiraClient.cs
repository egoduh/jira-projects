using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using JiraProjects.Models;

namespace JiraProjects;

/// <summary>
/// Тонкий клиент к Jira Server/DC 8.13.20 REST API v2.
/// Аутентификация: Bearer (токен Kantega SSO Enterprise) либо Basic.
/// </summary>
public sealed class JiraClient : IDisposable
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNameCaseInsensitive = true
    };

    private readonly HttpClient _http;

    public JiraClient(JiraOptions options)
    {
        options.Validate();

        var handler = new HttpClientHandler();
        if (options.InsecureSkipTlsVerify)
            handler.ServerCertificateCustomValidationCallback = HttpClientHandler.DangerousAcceptAnyServerCertificateValidator;

        _http = new HttpClient(handler)
        {
            BaseAddress = new Uri(options.BaseUrl.TrimEnd('/') + "/"),
            Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds)
        };

        _http.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        _http.DefaultRequestHeaders.Authorization = options.AuthMode switch
        {
            JiraAuthMode.Bearer => new AuthenticationHeaderValue("Bearer", options.Token),
            JiraAuthMode.Basic => new AuthenticationHeaderValue(
                "Basic",
                Convert.ToBase64String(Encoding.UTF8.GetBytes($"{options.Username}:{options.Token}"))),
            _ => throw new ArgumentOutOfRangeException(nameof(options.AuthMode))
        };
    }

    /// <summary>
    /// Список всех видимых текущему пользователю проектов.
    /// GET /rest/api/2/project — в 8.13.20 отдаёт весь массив без пагинации.
    /// </summary>
    public async Task<IReadOnlyList<JiraProject>> GetProjectsAsync(CancellationToken ct = default)
    {
        using var resp = await _http.GetAsync("rest/api/2/project", ct);
        await EnsureSuccessAsync(resp, ct);

        await using var stream = await resp.Content.ReadAsStreamAsync(ct);
        var projects = await JsonSerializer.DeserializeAsync<List<JiraProject>>(stream, JsonOpts, ct);
        return projects ?? new List<JiraProject>();
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage resp, CancellationToken ct)
    {
        if (resp.IsSuccessStatusCode) return;

        var body = await resp.Content.ReadAsStringAsync(ct);
        var hint = resp.StatusCode switch
        {
            HttpStatusCode.Unauthorized => " (401 — токен неверен/просрочен, либо режим auth не совпадает: Bearer vs Basic)",
            HttpStatusCode.Forbidden => " (403 — токен валиден, но нет прав/сработал CAPTCHA-lock)",
            HttpStatusCode.NotFound => " (404 — проверь BaseUrl и контекст-путь инстанса)",
            _ => ""
        };
        throw new HttpRequestException($"Jira вернула {(int)resp.StatusCode} {resp.ReasonPhrase}{hint}. Тело: {Truncate(body, 500)}");
    }

    private static string Truncate(string s, int max) => s.Length <= max ? s : s[..max] + "…";

    public void Dispose() => _http.Dispose();
}
