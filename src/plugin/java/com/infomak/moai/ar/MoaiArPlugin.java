package com.infomak.moai.ar;

import com.infomak.moai.contract.DrmInfo;
import com.infomak.moai.contract.IPlugin;
import com.infomak.moai.contract.PluginChannel;
import com.infomak.moai.contract.PluginManifest;
import com.infomak.moai.contract.ResolveRequest;
import com.infomak.moai.contract.ResolveResult;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Plugin .dex v1 — canales de Argentina resueltos con el enfoque de pascua.
 *
 * v1.1:
 *  - canal_7_salta  → HLS directo (sin DRM)
 *  - caze_fhd       → DASH CENC + ClearKey (licencia femon vía POST)
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
        CANALES = list;
    }

    public MoaiArPlugin() {
    }

    @Override
    public PluginManifest manifest() {
        return new PluginManifest(
            "moai_ar",
            "Moai Argentina",
            "1.1.0",
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
            // Resolución DIRECTA: HLS sin DRM (misma lógica de pascua).
            return new ResolveResult(
                "https://vivo.solumedia.com:2020/canal7salta/canal7salta.m3u8",
                headers,
                null,
                FORMAT_HLS,
                0L);
        }

        if ("caze_fhd".equals(channelId)) {
            // CLEARKEY vía licencia femon (misma lógica de pascua):
            //  1. DASH CENC con KID embebido en el MPD.
            //  2. DrmInfo("clearkey", licenciaUrl) → Media3 hace POST con
            //     {"kids":[base64url_kid]} → femon responde {"keys":[...]}.
            //  3. El UA va en el dsFactory (media + peticiones DRM).
            return new ResolveResult(
                "https://a12aivottepl-a.akamaihd.net/gru-nitro/live/dash/enc/"
                    + "3ynrpdanq2/out/v1/81fd4c26584044d2b1a1cc5b32fa9af0/cenc.mpd",
                headers,
                new DrmInfo("clearkey", CAZE_FEMON_LICENSE),
                FORMAT_DASH,
                0L);
        }

        throw new IllegalArgumentException("MoaiAr: canal desconocido " + channelId);
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