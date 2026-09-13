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
 * Plugin .dex v1 — canales de Argentina resueltos con el enfoque de pascua.
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

    // ---- Femon ClearKey: licencia devuelta por POST {"kids":[base64_kid]} ----
    // keyid (hex) = cenc:default_KID del MPD en uppercase sin guiones
    private static final String CAZE_FEMON_LICENSE =
        "https://results.femon.net/?keyid=34475edab991ad5e92548aebd710410a"
        + "&key=501b209cccd323ac00bf5ac15b406cb4";

    private static final String UNICANAL_FEMON_LICENSE =
        "https://results.femon.net/?keyid=63a3729cfd60f24f7e1266bee5eca02c"
        + "&key=cb9ed028af40654e1aa43934ee58db58";

    // ---- Flow token CDN (fidely a FlowTokenManager.DEFAULT_SEED_URLS) ----
    private static final String[] FLOW_SEED_URLS = {
        "https://cdn-py.cvattv.com.ar/live/c4eds/UNICANAL_C4/SA_Live_dash_enc/UNICANAL_C4.mpd",
        "https://chromecast.cvattv.com.ar/live/c6eds/Viajar/SA_Live_dash_cenc/Viajar.mpd",
        "https://cdn-py.cvattv.com.ar/live/c6eds/EWTN/SA_Live_dash_enc/EWTN.mpd",
        "https://cdn-py.cvattv.com.ar/live/c4eds/TELEFUTURO_C4/SA_Live_dash_enc/TELEFUTURO_C4.mpd",
    };

    private static final int MAX_REDIRECTS = 5;

    /** Regex para extraer tok_[...] del path (fiel a FlowTokenManager.TOK_PATTERN). */
    private static final Pattern TOK_PATTERN = Pattern.compile("/(tok_[^/]+)");
    /** Regex para extraer path relativo del canal (fiel a FlowTokenManager.PATH_PATTERN). */
    private static final Pattern PATH_PATTERN  = Pattern.compile("(live/c\\d+eds/[^?#]*)");
    private static final Pattern PATH_PATTERN_ALT = Pattern.compile("(c\\d+eds/[^?#]*)");

    // ---- Estado cacheado del token (volatile en Java; usamos synchronized) ----
    private static String sCachedHost;
    private static String sCachedTok;
    private static long   sCachedAt;
    private static long   sCachedTtl;

    private static final String UNICANAL_FLOW_SEED =
        "https://cdn-py.cvattv.com.ar/live/c4eds/UNICANAL_C4/"
        + "SA_Live_dash_enc/UNICANAL_C4.mpd";

    private static final List<PluginChannel> CANALES;
    static {
        List<PluginChannel> list = new ArrayList<PluginChannel>();
        list.add(new PluginChannel(
            "canal_7_salta",
            "7 Salta",
            "https://play-lh.googleusercontent.com/wqC28g5axDfQhkUhcALzgqvyF8bCwyCr06knFxa0FS0d0zy5lQG_9uC_ZQu-HJ-f9oXdFr4QJjGPZAUscuEwSQ",
            "Aire",
            "Argentina"));
        list.add(new PluginChannel(
            "caze_fhd",
            "CAZÉ TV FHD",
            "https://i.postimg.cc/XJjjwygm/cazetv-logo-0-2048x2048-Easy-Resize-com-(1).jpg",
            "Entretenimiento",
            "Argentina"));
        list.add(new PluginChannel(
            "unicanal_flow",
            "Unicanal Flow",
            "https://banners.femon.net/banners/6978d540a14188.24291079.png",
            "Entretenimiento",
            "Argentina"));
        CANALES = list;
    }

    public MoaiArPlugin() {
    }

    @Override
    public PluginManifest manifest() {
        return new PluginManifest(
            "moai_ar",
            "Moai Argentina",
            "1.2.0",
            1,
            1,
            CANALES,
            "com.infomak.moai.ar.MoaiArPlugin");
    }

    @Override
    public ResolveResult resolve(ResolveRequest request) {
        final String channelId = request.getChannelId();
        Map<String, String> headers = new LinkedHashMap<String, String>();
        headers.put("User-Agent", DEFAULT_UA);

        if ("canal_7_salta".equals(channelId)) {
            return new ResolveResult(
                "https://vivo.solumedia.com:2020/canal7salta/canal7salta.m3u8",
                headers,
                null,
                FORMAT_HLS,
                0L);
        }

        if ("caze_fhd".equals(channelId)) {
            return new ResolveResult(
                "https://a12aivottepl-a.akamaihd.net/gru-nitro/live/dash/enc/"
                    + "3ynrpdanq2/out/v1/81fd4c26584044d2b1a1cc5b32fa9af0/cenc.mpd",
                headers,
                new DrmInfo("clearkey", CAZE_FEMON_LICENSE),
                FORMAT_DASH,
                0L);
        }

        if ("unicanal_flow".equals(channelId)) {
            // FLOW: probe seeds → token CDN → URL firmada.
            final String relPath = extractRelativePath(UNICANAL_FLOW_SEED);

            String[] token = getFreshToken();
            if (token == null) {
                throw new RuntimeException("MoaiAr: no se obtuvo token Flow CDN");
            }
            final String host = token[0];
            final String tok  = token[1];

            final String signedUrl =
                "https://" + host + "/" + tok + "/" + relPath;

            // Headers para la CDN Flow (fiel a hydrateFlowHeaders / chooseHeaders).
            headers.put("Origin",  "https://portal.app.flow.com.ar");
            headers.put("Referer", "https://portal.app.flow.com.ar/");

            return new ResolveResult(
                signedUrl,
                headers,
                new DrmInfo("clearkey", UNICANAL_FEMON_LICENSE),
                FORMAT_DASH,
                0L);
        }

        throw new IllegalArgumentException("MoaiAr: canal desconocido " + channelId);
    }

    // ------------------------------------------------------------------ FLOW
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
