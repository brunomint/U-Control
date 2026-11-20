package com.ucontrol.equipe

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Um U-Control que respondeu em /api/identidade (blueprints/app_equipe.py). */
data class Igreja(val endereco: String, val nome: String, val versao: String, val id: String = "") {
    /** Nome para mostrar: o da igreja, ou o endereço se ela não tiver nome. */
    val titulo: String get() = nome.ifBlank { endereco.substringAfter("://") }
}

/** O servidor escolhido fica salvo; nas próximas vezes o app abre direto nele. */
object Servidor {
    const val PORTA = 8585
    private const val PREFS = "servidor"

    fun salvo(ctx: Context): Igreja? {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val endereco = p.getString("endereco", null) ?: return null
        return Igreja(endereco, p.getString("nome", "") ?: "", p.getString("versao", "") ?: "")
    }

    fun salvar(ctx: Context, igreja: Igreja) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString("endereco", igreja.endereco)
            .putString("nome", igreja.nome)
            .putString("versao", igreja.versao)
            .apply()
    }

    fun esquecer(ctx: Context) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
    }

    /**
     * O que a pessoa digitou vira um endereço completo:
     * "192.168.0.50" → http://192.168.0.50:8585, "ucontrol.local:8585" → http://…,
     * "minhaigreja.com" → https://minhaigreja.com (pela internet é sempre https).
     */
    fun normalizar(texto: String): String? {
        var t = texto.trim().trimEnd('/')
        if (t.isEmpty() || t.contains(' ')) return null
        if (!t.contains("://")) {
            val host = t.substringBefore('/').substringBefore(':')
            val local = host.matches(Regex("""\d{1,3}(\.\d{1,3}){3}""")) || host.endsWith(".local")
            t = if (local) {
                val comPorta = if (t.substringBefore('/').contains(':')) t else "$host:$PORTA" + t.removePrefix(host)
                "http://$comPorta"
            } else {
                "https://$t"
            }
        }
        return t
    }

    /** Pergunta "você é um U-Control?". Roda fora da tela principal (faz rede). */
    fun identificar(endereco: String, esperaMs: Int = 2500): Igreja? {
        return try {
            val con = URL("$endereco/api/identidade").openConnection() as HttpURLConnection
            con.connectTimeout = esperaMs
            con.readTimeout = esperaMs
            con.instanceFollowRedirects = false
            try {
                if (con.responseCode != 200) return null
                val json = JSONObject(con.inputStream.bufferedReader().use { it.readText() })
                if (json.optString("app") != "U-Control") return null
                Igreja(endereco, json.optString("igreja"), json.optString("versao"), json.optString("id"))
            } finally {
                con.disconnect()
            }
        } catch (e: Exception) {
            null
        }
    }
}
