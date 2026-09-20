package com.infomak.moai.ar;

import com.infomak.moai.contract.DrmInfo;
import com.infomak.moai.contract.IPlugin;
import com.infomak.moai.contract.PluginChannel;
import com.infomak.moai.contract.PluginManifest;
import com.infomak.moai.contract.ResolveRequest;
import com.infomak.moai.contract.ResolveResult;

import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Plugin .dex v1 — catálogo completo (449 canales desde master.json de pascua).
 *
 * v1.4.1:
 *  - Soporte de tag "ar" en manifest para identificación visual en moai3.
 *
 * v1.4.0:
 *  - Reorganización completa de categorías (Aire, Interior, Deportes, Radios, etc.).
 *  - Corrección de países (Brasil, Canadá, Internacional).
 *  - Ordenamiento lógico por importancia y relevancia de canales en cada categoría.
 *  - Actualización masiva de logos hacia CDN GitHub Raw tv-logos.
 *
 * v1.3.2:
 *  - Saneamiento y sustitución de URLs de logos caídas (403 Cloudflare) por fuentes estables CDN.
 *
 * v1.3.1:
 *  - Soporte de ClearKey DRM inline (data URI JSON) local sin depender de servidor externo.
 *
 * v1.3.0:
 *  - Catálogo íntegro generado por tools/generate_catalog.py.
 *  - resolve() genérico por canal: decide HLS / DASH / FLOW / ClearKey
 *    (inline kid:k convertido a licencia feemon: el motor solo sabe "clearkey").
 *
 * v1.2.1:
 *  - unicanal_flow: seed Viajar/chromecast (edge-liveXX responde, cde-py 403)
 *    + keyid femon correcto (7d798b4e) del MPD CDN real.
 *
 * v1.2:
 *  - canal_7_salta  → HLS directo (sin DRM)
 *  - caze_fhd       → DASH CENC + ClearKey (licencia femon vía POST)
 *  - unicanal_flow  → Flow CDN token (tok_) + DASH CENC + ClearKey femon
 *
 * El plugin SOLO resuelve la señal; el motor la reproduce.
 */
public final class MoaiArPlugin implements IPlugin {

    private static final String DEFAULT_UA =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            + "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36";
    private static final String FORMAT_HLS = "hls";
    private static final String FORMAT_DASH = "dash";

    // ---- Flow token CDN (fiel a FlowTokenManager.DEFAULT_SEED_URLS) ----
    // El orden replica EXACTAMENTE FlowTokenManager.DEFAULT_SEED_URLS: la
    // semilla chromecast/Viajar cae en edge-liveXX (responde), mientras cdn-py
    // cae en edgeXX-cde-py (403 en el dispositivo).
    private static final String[] FLOW_SEED_URLS = {
        "https://chromecast.cvattv.com.ar/live/c6eds/Viajar/SA_Live_dash_cenc/Viajar.mpd",
        "https://cdn-py.cvattv.com.ar/live/c6eds/EWTN/SA_Live_dash_enc/EWTN.mpd",
        "https://cdn-py.cvattv.com.ar/live/c4eds/UNICANAL_C4/SA_Live_dash_enc/UNICANAL_C4.mpd",
        "https://cdn-py.cvattv.com.ar/live/c4eds/TELEFUTURO_C4/SA_Live_dash_enc/TELEFUTURO_C4.mpd",
    };

    private static final int MAX_REDIRECTS = 5;

    /** Regex para extraer tok_[...] del path (fiel a FlowTokenManager.TOK_PATTERN). */
    private static final Pattern TOK_PATTERN = Pattern.compile("/(tok_[^/]+)");
    /** Regex para extraer path relativo del canal (fiel a FlowTokenManager.PATH_PATTERN). */
    private static final Pattern PATH_PATTERN  = Pattern.compile("(live/c\\d+eds/[^?#]*)");
    private static final Pattern PATH_PATTERN_ALT = Pattern.compile("(c\\d+eds/[^?#]*)");

    // ---- hosts / marcadores para detectar el sistema de cada canal ----
    private static final String[] FLOW_MARKERS = {
        "cvattv.com.ar", "cvattv.com.py", "flow.com.ar", "flow.com.py",
        "cdn-token.app.flow.com.ar",
    };

    // ---- Estado cacheado del token (volatile en Java; usamos synchronized) ----
    private static String sCachedHost;
    private static String sCachedTok;
    private static long   sCachedAt;
    private static long   sCachedTtl;

    private static final List<PluginChannel> CANALES;
    static {
        List<PluginChannel> list = new ArrayList<PluginChannel>();
        for (MoaiCatalog.Entrada e : MoaiCatalog.all()) {
            list.add(new PluginChannel(
                e.id, e.nombre, e.logo, e.categoria, e.pais));
        }
        CANALES = list;
    }

    public MoaiArPlugin() {
    }

    @Override
    public PluginManifest manifest() {
        return new PluginManifest(
            "moai_ar",
            "Moai Argentina",
            "1.4.1",
            1,
            1,
            CANALES,
            "com.infomak.moai.ar.MoaiArPlugin");
    }

    @Override
    public ResolveResult resolve(ResolveRequest request) {
        final String channelId = request.getChannelId();
        final MoaiCatalog.Entrada e = MoaiCatalog.byId(channelId);
        if (e == null) {
            throw new IllegalArgumentException("MoaiAr: canal desconocido " + channelId);
        }

        Map<String, String> headers = new LinkedHashMap<String, String>();
        headers.put("User-Agent", DEFAULT_UA);
        for (Map.Entry<String, String> h : e.headers.entrySet()) {
            headers.put(h.getKey(), h.getValue());
        }

        String url = e.url;
        final boolean flow = isFlow(e.url);
        if (flow) {
            String[] token = getFreshToken();
            if (token == null) {
                throw new RuntimeException("MoaiAr: no se obtuvo token Flow CDN");
            }
            final String relPath = extractRelativePath(e.url);
            url = "https://" + token[0] + "/" + token[1] + "/" + relPath;
            // Headers para la CDN Flow (fiel a hydrateFlowHeaders / chooseHeaders).
            headers.put("Origin",  "https://portal.app.flow.com.ar");
            headers.put("Referer", "https://portal.app.flow.com.ar/");
        }

        final String format = (url.toLowerCase().endsWith(".m3u8")
                || url.toLowerCase().contains(".m3u8?"))
            ? FORMAT_HLS : FORMAT_DASH;

        DrmInfo drm = drmFor(e.drm);

        return new ResolveResult(url, headers, drm, format, 0L);
    }

    // ------------------------------------------------------------------ DRM
    /**
     * Convierte la licencia del catálogo a un [DrmInfo].
     *  - '' -> null (sin DRM).
     *  - URL ya formada (femon/Widevine) -> se pasa tal cual (clearkey).
     *  - 'kid:<b64url>,k:<b64url>' -> data:application/json inline con claves ClearKey
     *    (el motor de moai3 lo consume mediante LocalMediaDrmCallback sin red).
     */
    private static DrmInfo drmFor(String drm) {
        if (drm == null || drm.trim().isEmpty()) return null;
        final String d = drm.trim();

        // URL externa ya formada (femon/Widevine) -> se pasa tal cual.
        if (d.startsWith("https://") || d.startsWith("http://")) {
            return new DrmInfo("clearkey", d);
        }

        // Formato kid:<b64url>,k:<b64url> -> ClearKey JSON inline
        String kid = null;
        String key = null;
        for (String part : d.split(",")) {
            part = part.trim();
            if (part.startsWith("kid:")) {
                kid = part.substring(4).trim();
            } else if (part.startsWith("k:")) {
                key = part.substring(2).trim();
            } else if (part.startsWith("keyid:")) {
                kid = part.substring(6).trim();
            } else if (part.startsWith("key:")) {
                key = part.substring(4).trim();
            }
        }
        // Un caso raro del catálogo: "DDl3j-j7T5-FdAFrPUri7Q,k:..." (sin prefijo kid:)
        if (kid == null && !d.contains("k:")) {
            kid = d;
        }
        if (kid == null || key == null) return null;

        String json = "{\"keys\":[{\"kty\":\"oct\",\"k\":\"" + key + "\",\"kid\":\"" + kid + "\"}],\"type\":\"temporary\"}";
        return new DrmInfo("clearkey", "data:application/json," + json);
    }

    /** base64url (sin padding) -> hex. */
    private static String b64urlToHex(String s) {
        final String alphabet =
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
        int bits = 0;
        int accum = 0;
        StringBuilder hex = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            int val = alphabet.indexOf(s.charAt(i));
            if (val < 0) continue;
            accum = (accum << 6) | val;
            bits += 6;
            if (bits >= 8) {
                bits -= 8;
                hex.append(String.format("%02x", (accum >> bits) & 0xff));
            }
        }
        return hex.toString();
    }

    // ------------------------------------------------------------------ FLOW
    private static boolean isFlow(String url) {
        final String lower = url.toLowerCase();
        for (String marker : FLOW_MARKERS) {
            if (lower.contains(marker)) return true;
        }
        return false;
    }

    /**
     * Devuelve [host, tok] cacheando por ~45-60 s.
     * Fiel a FlowTokenManager.getFreshToken/refreshToken.
     */
    private static synchronized String[] getFreshToken() {
        final long now = System.currentTimeMillis();
        if (sCachedHost != null && sCachedTok != null && now - sCachedAt < sCachedTtl) {
            return new String[]{ sCachedHost, sCachedTok };
        }
        for (String seedUrl : FLOW_SEED_URLS) {
            try {
                String[] info = probeSeed(seedUrl);
                if (info != null) {
                    sCachedHost = info[0];
                    sCachedTok  = info[1];
                    sCachedAt   = now;
                    sCachedTtl  = 45000 + new Random().nextInt(15000);
                    return info;
                }
            } catch (Exception e) {
                System.err.println("[MoaiAr] seed failed " + seedUrl + ": " + e);
            }
        }
        return null;
    }

    /**
     * Sigue redirects manualmente (max 5) con followRedirects=false,
     * como FlowTokenManager.probeSeed. Extrae tok_... del Location.
     */
    private static String[] probeSeed(String seedUrl) throws Exception {
        String currentUrl = seedUrl;
        for (int hop = 0; hop < MAX_REDIRECTS; hop++) {
            HttpURLConnection conn =
                (HttpURLConnection) new URL(currentUrl).openConnection();
            try {
                conn.setInstanceFollowRedirects(false);
                conn.setRequestProperty("User-Agent", DEFAULT_UA);
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(10000);

                int code = conn.getResponseCode();
                String location = conn.getHeaderField("Location");

                if (location != null && !location.isEmpty()) {
                    String[] info = extractTok(location);
                    if (info != null) return info;
                }

                if (code < 301 || code > 308) {
                    // No redirect: intenta extraer del URL actual.
                    return extractTok(currentUrl);
                }

                if (location == null || location.isEmpty()) return null;
                currentUrl = resolveRelative(currentUrl, location);
            } finally {
                conn.disconnect();
            }
        }
        return null;
    }

    /** Extrae [host, tok] de un path que contiene /tok_[...]. */
    private static String[] extractTok(String location) {
        Matcher m = TOK_PATTERN.matcher(location);
        if (!m.find()) return null;
        try {
            URL u = new URL(location);
            String host = u.getHost(); // sin puerto
            String tok  = m.group(1);
            return new String[]{ host, tok };
        } catch (Exception e) {
            return null;
        }
    }

    /** Fiel a FlowTokenManager.extractRelativePath. */
    private static String extractRelativePath(String url) {
        Matcher m = PATH_PATTERN.matcher(url);
        if (m.find()) return m.group(1);
        Matcher m2 = PATH_PATTERN_ALT.matcher(url);
        if (m2.find()) return "live/" + m2.group(1);
        return "";
    }

    private static String resolveRelative(String baseUrl, String relative) {
        if (relative.startsWith("http://") || relative.startsWith("https://")) {
            return relative;
        }
        try {
            return new URL(new URL(baseUrl), relative).toString();
        } catch (Exception e) {
            return relative;
        }
    }

    // --------------------------------------------------------- autotest (JVM)
    public static void main(String[] args) throws Exception {
        MoaiArPlugin p = new MoaiArPlugin();
        System.out.println("manifest: " + p.manifest());
        for (PluginChannel ch : p.manifest().getCanales()) {
            System.out.println("--- " + ch.getNombre() + " ---");
            ResolveResult r = p.resolve(new ResolveRequest(ch.getId(), 0));
            System.out.println("resolve: " + r);
        }
    }
}