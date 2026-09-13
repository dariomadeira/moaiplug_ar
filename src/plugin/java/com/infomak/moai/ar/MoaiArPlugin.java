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
 * v1: SOLO resolución DIRECTA (canal 7 Salta, HLS sin DRM ni token). El plugin
 * devuelve la URL tal cual más el User-Agent por defecto de pascua; el motor de
 * moai3 la reproduce. Próximos pasos (misma estructura): canal CLEARKEY y canal
 * FLOW (con token CDN).
 *
 * El plugin SOLO resuelve la señal; el motor la reproduce tal cual.
 */
public final class MoaiArPlugin implements IPlugin {

    private static final String DEFAULT_UA =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            + "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36";
    private static final String FORMAT_HLS = "hls";

    private static final List<PluginChannel> CANALES;
    static {
        List<PluginChannel> list = new ArrayList<PluginChannel>();
        list.add(new PluginChannel(
            "canal_7_salta",
            "7 Salta",
            "https://play-lh.googleusercontent.com/wqC28g5axDfQhkUhcALzgqvyF8bCwyCr06knFxa0FS0d0zy5lQG_9uC_ZQu-HJ-f9oXdFr4QJjGPZAUscuEwSQ",
            "Aire",
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
            "1.0.0",
            1,
            1,
            CANALES,
            "com.infomak.moai.ar.MoaiArPlugin");
    }

    @Override
    public ResolveResult resolve(ResolveRequest request) {
        final String channelId = request.getChannelId();
        if ("canal_7_salta".equals(channelId)) {
            // Resolución DIRECTA de pascua: la URL se usa tal cual (HLS, sin DRM).
            Map<String, String> headers = new LinkedHashMap<String, String>();
            headers.put("User-Agent", DEFAULT_UA);
            return new ResolveResult(
                "https://vivo.solumedia.com:2020/canal7salta/canal7salta.m3u8",
                headers,
                null,
                FORMAT_HLS,
                0L);
        }
        throw new IllegalArgumentException("MoaiAr: canal desconocido " + channelId);
    }

    // --------------------------------------------------------- autotest (JVM)
    public static void main(String[] args) throws Exception {
        MoaiArPlugin p = new MoaiArPlugin();
        System.out.println("manifest: " + p.manifest());
        ResolveResult r = p.resolve(new ResolveRequest("canal_7_salta", 0));
        System.out.println("resolve: " + r);
    }
}