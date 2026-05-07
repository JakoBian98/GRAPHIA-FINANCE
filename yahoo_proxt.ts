/**
 * Graphia Finance — Yahoo Finance Deno Deploy Proxy
 * ==================================================
 * GAS + CF Workers'a ek üçüncü proxy katmanı.
 * Deno'nun kendi edge IP'lerinden Yahoo'ya bağlanır.
 *
 * Deno KV ile session cache (built-in, kurulum gerektirmez)
 * API format: ?url=encoded_yahoo_url&key=API_KEY
 */

const SESSION_TTL_MS = 25 * 60 * 1000;

const ALLOWED_HOSTS = [
  "query1.finance.yahoo.com",
  "query2.finance.yahoo.com",
  "finance.yahoo.com",
];

const ALLOWED_PATHS = [
  "/v8/finance/chart",
  "/v10/finance/quoteSummary",
  "/v7/finance/download",
  "/v11/finance/quoteSummary",
  "/v6/finance/quote",
  "/v7/finance/quote",
  "/v1/finance/search",
  "/v1/test/getcrumb",
  "/v10/finance/options",
];

const USER_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
];

function randomUA(): string {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function getHeaders(cookie: string, referer: string, isNav = false): Record<string, string> {
  const h: Record<string, string> = {
    "User-Agent": randomUA(),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Chromium";v="134", "Google Chrome";v="134", "Not;A=Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
  };
  if (isNav) {
    h["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8";
    h["Sec-Fetch-Site"] = "none";
    h["Sec-Fetch-Mode"] = "navigate";
    h["Sec-Fetch-Dest"] = "document";
    h["Upgrade-Insecure-Requests"] = "1";
  } else {
    h["Accept"] = "application/json, text/plain, */*";
    h["Sec-Fetch-Site"] = "same-site";
    h["Sec-Fetch-Mode"] = "cors";
    h["Sec-Fetch-Dest"] = "empty";
    h["Referer"] = referer || "https://finance.yahoo.com/";
    h["Origin"] = "https://finance.yahoo.com";
  }
  if (cookie) h["Cookie"] = cookie;
  return h;
}

function mergeCookies(existing: string, setCookieArr: string[]): string {
  const map: Record<string, string> = {};
  const parse = (str: string) => {
    const part = str.split(";")[0].trim();
    const idx = part.indexOf("=");
    if (idx > 0) map[part.substring(0, idx).trim()] = part.substring(idx + 1).trim();
  };
  if (existing) existing.split("; ").forEach(parse);
  setCookieArr.forEach(parse);
  return Object.entries(map).map(([k, v]) => `${k}=${v}`).join("; ");
}

function getSetCookies(response: Response): string[] {
  return response.headers.getSetCookie?.() ?? [];
}

// ── Deno KV session cache ─────────────────────────────────────
const kv = await Deno.openKv();
const KV_KEY = ["yahoo_deno_session"];

async function loadSession(): Promise<{ cookie: string; crumb: string; ts: number } | null> {
  try {
    const entry = await kv.get<{ cookie: string; crumb: string; ts: number }>(KV_KEY);
    if (!entry.value) return null;
    if (Date.now() - entry.value.ts > SESSION_TTL_MS) return null;
    return entry.value;
  } catch {
    return null;
  }
}

async function saveSession(cookie: string, crumb: string): Promise<void> {
  try {
    await kv.set(KV_KEY, { cookie, crumb, ts: Date.now() }, { expireIn: SESSION_TTL_MS });
  } catch { /* ignore */ }
}

async function buildFreshSession(): Promise<{ cookie: string; crumb: string }> {
  let cookie = "";

  // 1. Ana sayfa
  const r1 = await fetch("https://finance.yahoo.com/", {
    method: "GET",
    headers: getHeaders("", "", true),
    redirect: "follow",
  });
  cookie = mergeCookies(cookie, getSetCookies(r1));
  await sleep(700 + Math.floor(Math.random() * 500));

  // 2. GDPR consent
  const consent = "GUC=AQABCAFn__9n__9nVQT5&s=AQAAAMjH&g=AQA; GUCS=AQABCAFn__9n__9nVQT5; A1=d=AQABBCFn__9nECAA&S=AQAAAMjH; A3=d=AQABBCFn__9nECAA&S=AQAAAMjH";
  if (!cookie.includes("GUC=")) cookie = cookie ? cookie + "; " + consent : consent;

  // 3. Crumb al
  let crumb = "";
  const cr = await fetch("https://query2.finance.yahoo.com/v1/test/getcrumb", {
    method: "GET",
    headers: getHeaders(cookie, "https://finance.yahoo.com/"),
  });
  if (cr.status === 200) {
    const text = await cr.text();
    if (!text.includes("<") && text.trim().length >= 3) crumb = text.trim();
    cookie = mergeCookies(cookie, getSetCookies(cr));
  }

  await saveSession(cookie, crumb);
  return { cookie, crumb };
}

async function getSession(): Promise<{ cookie: string; crumb: string }> {
  const cached = await loadSession();
  if (cached?.crumb) return cached;
  return buildFreshSession();
}

function makeError(msg: string, status = 400): Response {
  return new Response(JSON.stringify({ error: msg, deno_status: status }), {
    status,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
}

// ── Ana handler ───────────────────────────────────────────────
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET" } });
  }

  const url = new URL(req.url);

  // API key kontrolü
  const apiKey = Deno.env.get("API_KEY") ?? "";
  const reqKey = url.searchParams.get("key") ?? "";
  if (apiKey && reqKey !== apiKey) return makeError("Unauthorized", 403);

  const targetUrl = decodeURIComponent(url.searchParams.get("url") ?? "");
  if (!targetUrl) return makeError("url parametresi eksik");

  // Host güvenlik
  let host = "";
  try { host = new URL(targetUrl).hostname; } catch { /**/ }
  if (!ALLOWED_HOSTS.includes(host)) return makeError("Host izinli degil: " + host, 403);

  // Path güvenlik
  let path = "";
  try { path = new URL(targetUrl).pathname; } catch { /**/ }
  if (!ALLOWED_PATHS.some((p) => path.startsWith(p))) return makeError("Path izinli degil: " + path, 403);

  try {
    let { cookie, crumb } = await getSession();

    if (path === "/v1/test/getcrumb") {
      return new Response(crumb || "", {
        headers: { "Content-Type": "text/plain", "Access-Control-Allow-Origin": "*" },
      });
    }

    // Ticker referer
    const tm = targetUrl.match(/\/(?:chart|quoteSummary|download)\/([^?/]+)/);
    const ticker = tm?.[1] ?? "";
    const referer = ticker
      ? `https://finance.yahoo.com/quote/${ticker}/`
      : "https://finance.yahoo.com/markets/";

    // Crumb'u Deno session'ınkiyle değiştir
    let finalUrl = targetUrl.replace(/[?&]crumb=[^&]*/g, "");
    if (crumb) finalUrl += (finalUrl.includes("?") ? "&" : "?") + "crumb=" + encodeURIComponent(crumb);

    await sleep(200 + Math.floor(Math.random() * 300));

    const dataResp = await fetch(finalUrl, {
      method: "GET",
      headers: getHeaders(cookie, referer),
    });
    const content = await dataResp.text();

    // 401 → session sıfırla, tekrar dene
    if (dataResp.status === 401) {
      await kv.delete(KV_KEY);
      const fresh = await buildFreshSession();
      let retryUrl = targetUrl.replace(/[?&]crumb=[^&]*/g, "");
      if (fresh.crumb) retryUrl += (retryUrl.includes("?") ? "&" : "?") + "crumb=" + encodeURIComponent(fresh.crumb);
      const retry = await fetch(retryUrl, { method: "GET", headers: getHeaders(fresh.cookie, referer) });
      return new Response(await retry.text(), {
        status: retry.status,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      });
    }

    return new Response(content, {
      status: dataResp.status,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });

  } catch (err) {
    return makeError("Deno fetch hatası: " + String(err), 502);
  }
});
