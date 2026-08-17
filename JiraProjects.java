import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSession;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.KeyStore;
import java.security.SecureRandom;
import java.security.cert.Certificate;
import java.security.cert.CertificateException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import javax.net.ssl.TrustManagerFactory;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Локальный веб-сайт со списком проектов Jira Server/DC 8.13.20.
 *
 * Один файл, только стандартная библиотека JDK — ни Maven/Gradle, ни зависимостей.
 * Встроенный com.sun.net.httpserver отдаёт страницу, а /api/projects проксирует
 * сырой JSON из Jira (GET /rest/api/2/project) — парсит его уже браузер, поэтому
 * JSON-библиотека в Java не нужна. Это же снимает проблему CORS и не светит токен.
 *
 * Запуск (Java 11+, без компиляции):
 *     java JiraProjects.java
 * либо с компиляцией (любой JDK):
 *     javac JiraProjects.java && java JiraProjects
 *
 * Конфиг — из .env рядом со скриптом или из переменных окружения:
 *     JIRA_BASE_URL, JIRA_TOKEN, JIRA_AUTH_MODE(bearer|basic),
 *     JIRA_USERNAME, JIRA_INSECURE(1), JIRA_TIMEOUT(сек), PORT(8000)
 */
public class JiraProjects {

    static final Map<String, String> DOTENV = new HashMap<>();

    static String baseUrl, token, authMode, username;
    static boolean insecure;
    static int timeoutMs, port;

    public static void main(String[] args) throws Exception {
        loadDotEnv();
        baseUrl  = env("JIRA_BASE_URL", "").replaceAll("/+$", "");
        token    = env("JIRA_TOKEN", "");
        authMode = env("JIRA_AUTH_MODE", "bearer").toLowerCase();
        username = env("JIRA_USERNAME", "");
        insecure = Arrays.asList("1", "true", "yes").contains(env("JIRA_INSECURE", "").toLowerCase());
        timeoutMs = Integer.parseInt(env("JIRA_TIMEOUT", "30")) * 1000;
        port = Integer.parseInt(env("PORT", "8000"));

        if (baseUrl.isEmpty() || token.isEmpty()) {
            System.out.println("!  Не заданы JIRA_BASE_URL / JIRA_TOKEN — страница откроется, но покажет ошибку.");
        }
        configureTls();

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.createContext("/", JiraProjects::handle);
        server.setExecutor(null);
        server.start();
        System.out.println("Сайт со списком проектов: http://localhost:" + port + "  (Ctrl+C для остановки)");
    }

    static void handle(HttpExchange ex) throws IOException {
        String path = ex.getRequestURI().getPath();
        try {
            if (path.equals("/") || path.startsWith("/index")) {
                String page = readPage().replace("__BASEURL__", baseUrl);
                send(ex, 200, page, "text/html; charset=utf-8");
            } else if (path.startsWith("/api/projects")) {
                String json = fetchProjects();
                send(ex, 200, json, "application/json; charset=utf-8");
            } else if (path.startsWith("/api/whoami")) {
                // Диагностика: кто мы для Jira? 200 с данными юзера = токен принят;
                // 401/аноним = токен не применился (частая причина пустого списка проектов).
                String json = jiraGet("/rest/api/2/myself");
                send(ex, 200, json, "application/json; charset=utf-8");
            } else {
                send(ex, 404, "{\"error\":\"not found\"}", "application/json; charset=utf-8");
            }
        } catch (JiraError e) {
            send(ex, 502, "{\"error\":" + jsonStr(e.getMessage()) + "}", "application/json; charset=utf-8");
        } catch (Exception e) {
            send(ex, 502, "{\"error\":" + jsonStr(String.valueOf(e.getMessage())) + "}", "application/json; charset=utf-8");
        }
    }

    /** Сырой JSON-массив проектов из Jira. Парсит браузер. */
    static String fetchProjects() throws Exception {
        String body = jiraGet("/rest/api/2/project");
        if (body.trim().equals("[]")) {
            System.out.println("!  Jira вернула пустой список ([]). Вероятно, токен не применился и запрос "
                    + "ушёл как анонимный — открой http://localhost:" + port + "/api/whoami для проверки.");
        }
        return body;
    }

    /** GET к Jira REST с авторизацией. Возвращает тело, кидает JiraError с подсказкой. */
    static String jiraGet(String apiPath) throws Exception {
        if (baseUrl.isEmpty()) throw new JiraError("Не задан JIRA_BASE_URL");
        if (token.isEmpty()) throw new JiraError("Не задан JIRA_TOKEN");
        if (authMode.equals("basic") && username.isEmpty())
            throw new JiraError("Для JIRA_AUTH_MODE=basic нужен JIRA_USERNAME");

        URL u = new URL(baseUrl + apiPath);
        HttpURLConnection c = (HttpURLConnection) u.openConnection();
        c.setRequestMethod("GET");
        c.setConnectTimeout(timeoutMs);
        c.setReadTimeout(timeoutMs);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("Authorization", authHeader());

        int code;
        try {
            code = c.getResponseCode();
        } catch (Exception e) {
            throw new JiraError("Сетевая ошибка: " + e.getMessage() + ". При self-signed сертификате задай JIRA_INSECURE=1 или JIRA_CACERT");
        }
        InputStream is = code >= 400 ? c.getErrorStream() : c.getInputStream();
        String body = is == null ? "" : readAll(is);
        if (code >= 400) {
            String hint = code == 401 ? " (токен неверен/просрочен либо режим auth не совпадает: bearer vs basic)"
                    : code == 403 ? " (нет прав / CAPTCHA-lock)"
                    : code == 404 ? " (проверь JIRA_BASE_URL и контекст-путь)" : "";
            // Jira/Seraph кладут причину отказа в заголовки — самое ценное для диагностики
            StringBuilder diag = new StringBuilder();
            for (String h : new String[]{"WWW-Authenticate", "X-Seraph-LoginReason",
                    "X-Authentication-Denied-Reason", "X-AUSERNAME"}) {
                String v = c.getHeaderField(h);
                if (v != null) diag.append(" [").append(h).append(": ").append(v).append("]");
            }
            throw new JiraError("Jira вернула " + code + hint + "." + diag + " " + trunc(body, 300));
        }
        return body;
    }

    // --- вспомогательное ---

    static String readPage() throws IOException {
        Path p = Paths.get("index.html");
        if (!Files.exists(p)) throw new IOException("рядом нет index.html — запускай из папки проекта");
        return new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
    }

    static void send(HttpExchange ex, int code, String body, String ctype) throws IOException {
        byte[] b = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", ctype);
        ex.sendResponseHeaders(code, b.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(b);
        }
    }

    static String env(String key, String def) {
        String v = System.getenv(key);
        if (v == null || v.isEmpty()) v = DOTENV.get(key);
        return (v == null || v.isEmpty()) ? def : v;
    }

    static void loadDotEnv() {
        try {
            Path p = Paths.get(".env");
            if (!Files.exists(p)) return;
            for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
                String t = line.trim();
                if (t.isEmpty() || t.startsWith("#") || !t.contains("=")) continue;
                int i = t.indexOf('=');
                String k = t.substring(0, i).trim();
                String val = t.substring(i + 1).trim();
                if (val.length() >= 2 && ((val.startsWith("\"") && val.endsWith("\""))
                        || (val.startsWith("'") && val.endsWith("'")))) {
                    val = val.substring(1, val.length() - 1);
                }
                DOTENV.put(k, val);
            }
        } catch (IOException ignored) {
        }
    }

    /**
     * Заголовок Authorization по режиму:
     *   basic          -> Basic base64(логин:токен)
     *   ksso           -> ksso-token &lt;токен&gt;   (нативная схема Kantega SSO Enterprise)
     *   bearer (деф.)  -> Bearer &lt;токен&gt;
     * JIRA_AUTH_SCHEME задаёт произвольное имя схемы (если админ настроил своё):
     *   Authorization: &lt;scheme&gt; &lt;токен&gt;
     */
    static String authHeader() {
        if (authMode.equals("basic")) return "Basic " + base64(username + ":" + token);
        String scheme = env("JIRA_AUTH_SCHEME", "");
        if (!scheme.isEmpty()) return scheme + " " + token;
        if (authMode.equals("ksso") || authMode.equals("ksso-token")) return "ksso-token " + token;
        return "Bearer " + token;
    }

    static String base64(String s) {
        return java.util.Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8));
    }

    static String readAll(InputStream is) throws IOException {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = is.read(buf)) != -1) bos.write(buf, 0, n);
        return new String(bos.toByteArray(), StandardCharsets.UTF_8);
    }

    static String trunc(String s, int max) {
        if (s == null) return "";
        return s.length() <= max ? s : s.substring(0, max) + "…";
    }

    static String jsonStr(String s) {
        if (s == null) s = "";
        StringBuilder sb = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            switch (ch) {
                case '"':  sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (ch < 0x20) sb.append(String.format("\\u%04x", (int) ch));
                    else sb.append(ch);
            }
        }
        return sb.append("\"").toString();
    }

    /**
     * Три режима TLS:
     *   JIRA_INSECURE=1        — не проверять сертификат вообще (последнее средство);
     *   JIRA_CACERT=путь       — доверять этому корпоративному CA (PEM/CRT) + системным (правильно);
     *   по умолчанию           — только системный truststore JDK (для публичных CA).
     */
    static void configureTls() throws Exception {
        if (insecure) {
            trustAllCerts();
            System.out.println("TLS: проверка сертификата ОТКЛЮЧЕНА (JIRA_INSECURE).");
            return;
        }
        String caPath = env("JIRA_CACERT", "");
        if (!caPath.isEmpty()) {
            installCustomCa(caPath);
            System.out.println("TLS: добавлен корпоративный CA из " + caPath);
        }
    }

    static void trustAllCerts() throws Exception {
        TrustManager[] tm = {new X509TrustManager() {
            public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            public void checkClientTrusted(X509Certificate[] chain, String authType) { }
            public void checkServerTrusted(X509Certificate[] chain, String authType) { }
        }};
        SSLContext sc = SSLContext.getInstance("TLS");
        sc.init(null, tm, new SecureRandom());
        HttpsURLConnection.setDefaultSSLSocketFactory(sc.getSocketFactory());
        HttpsURLConnection.setDefaultHostnameVerifier(new HostnameVerifier() {
            public boolean verify(String hostname, SSLSession session) { return true; }
        });
    }

    /** Доверять переданному CA-файлу (один или несколько PEM/CRT) в дополнение к системным. */
    static void installCustomCa(String path) throws Exception {
        CertificateFactory cf = CertificateFactory.getInstance("X.509");
        Collection<? extends Certificate> certs;
        try (InputStream in = Files.newInputStream(Paths.get(path))) {
            certs = cf.generateCertificates(in);
        }
        if (certs.isEmpty()) throw new Exception("В файле CA нет сертификатов: " + path);

        KeyStore ks = KeyStore.getInstance(KeyStore.getDefaultType());
        ks.load(null, null);
        int i = 0;
        for (Certificate cert : certs) ks.setCertificateEntry("ca" + (i++), cert);

        final X509TrustManager custom = firstX509(ks);
        final X509TrustManager system = firstX509(null);

        X509TrustManager composite = new X509TrustManager() {
            public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                system.checkClientTrusted(chain, authType);
            }
            public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                try {
                    system.checkServerTrusted(chain, authType);       // сначала системные CA
                } catch (CertificateException e) {
                    custom.checkServerTrusted(chain, authType);        // затем корпоративный
                }
            }
            public X509Certificate[] getAcceptedIssuers() {
                List<X509Certificate> all = new ArrayList<>();
                all.addAll(Arrays.asList(system.getAcceptedIssuers()));
                all.addAll(Arrays.asList(custom.getAcceptedIssuers()));
                return all.toArray(new X509Certificate[0]);
            }
        };

        SSLContext sc = SSLContext.getInstance("TLS");
        sc.init(null, new TrustManager[]{composite}, new SecureRandom());
        HttpsURLConnection.setDefaultSSLSocketFactory(sc.getSocketFactory());
    }

    /** Первый X509TrustManager из truststore ks (или системного, если ks == null). */
    static X509TrustManager firstX509(KeyStore ks) throws Exception {
        TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        tmf.init(ks);
        for (TrustManager tm : tmf.getTrustManagers()) {
            if (tm instanceof X509TrustManager) return (X509TrustManager) tm;
        }
        throw new Exception("Не найден X509TrustManager");
    }

    static class JiraError extends Exception {
        JiraError(String m) { super(m); }
    }
}
