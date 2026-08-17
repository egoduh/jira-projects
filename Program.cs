using System.Text.Json;
using Microsoft.Extensions.Configuration;
using JiraProjects;

// Конфиг: appsettings.json (без секретов) -> user-secrets -> env (JIRA__TOKEN и т.п.).
// Флаг --json на выходе печатает сырой JSON вместо таблицы.
var asJson = args.Contains("--json");

var config = new ConfigurationBuilder()
    .SetBasePath(AppContext.BaseDirectory)
    .AddJsonFile("appsettings.json", optional: true)
    .AddUserSecrets(typeof(Program).Assembly, optional: true)
    .AddEnvironmentVariables()
    .Build();

var options = new JiraOptions();
config.GetSection("Jira").Bind(options);

try
{
    using var client = new JiraClient(options);
    var projects = await client.GetProjectsAsync();

    if (asJson)
    {
        Console.WriteLine(JsonSerializer.Serialize(projects, new JsonSerializerOptions { WriteIndented = true }));
    }
    else
    {
        Console.WriteLine($"Проектов: {projects.Count}\n");
        Console.WriteLine($"{"KEY",-12} {"NAME",-40} {"LEAD"}");
        Console.WriteLine(new string('-', 74));
        foreach (var p in projects.OrderBy(p => p.Key))
            Console.WriteLine($"{p.Key,-12} {Trim(p.Name, 40),-40} {p.Lead?.DisplayName ?? p.Lead?.Name ?? ""}");
    }
    return 0;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Ошибка: {ex.Message}");
    return 1;
}

static string Trim(string s, int max) => s.Length <= max ? s : s[..(max - 1)] + "…";
