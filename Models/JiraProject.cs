using System.Text.Json.Serialization;

namespace JiraProjects.Models;

/// <summary>
/// Проект Jira в том виде, в котором его отдаёт GET /rest/api/2/project.
/// В Jira 8.13.20 (Server/DC) это плоский список видимых текущему пользователю проектов.
/// </summary>
public sealed record JiraProject
{
    [JsonPropertyName("id")]
    public string Id { get; init; } = "";

    [JsonPropertyName("key")]
    public string Key { get; init; } = "";

    [JsonPropertyName("name")]
    public string Name { get; init; } = "";

    [JsonPropertyName("projectTypeKey")]
    public string? ProjectTypeKey { get; init; }

    [JsonPropertyName("lead")]
    public JiraUser? Lead { get; init; }

    [JsonPropertyName("archived")]
    public bool? Archived { get; init; }
}

public sealed record JiraUser
{
    [JsonPropertyName("name")]
    public string? Name { get; init; }

    [JsonPropertyName("displayName")]
    public string? DisplayName { get; init; }
}
