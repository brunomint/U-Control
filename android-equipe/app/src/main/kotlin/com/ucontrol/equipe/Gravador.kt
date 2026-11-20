package com.ucontrol.equipe

import android.annotation.SuppressLint
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import java.io.ByteArrayInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.Collections

/**
 * Salva uma página do U-Control como ela é: abre num navegador invisível e
 * guarda tudo o que ela carrega (o HTML, CSS, JS, fontes, a lista da ordem que
 * o JS busca…). Sem internet, a PaginaActivity entrega esses arquivos e a cifra
 * funciona igual — tom, partitura, rolagem —, sem copiar nada do U-Control
 * para dentro do app.
 *
 * Usar na tela principal (main thread), uma página por vez.
 */
class Gravador(ctx: Context, private val base: String, private val acervo: Acervo) {

    private val principal = Handler(Looper.getMainLooper())
    private var web: WebView? = null
    private val appCtx = ctx.applicationContext

    // Página em gravação. `geracao` separa o que chega atrasado da página anterior.
    @Volatile private var geracao = 0
    private var pagina = ""
    private var aoTerminar: ((Boolean) -> Unit)? = null
    private val recursos: MutableSet<String> = Collections.synchronizedSet(mutableSetOf())
    @Volatile private var principalOk = false
    @Volatile private var carregou = false
    private val pendentes = java.util.concurrent.atomic.AtomicInteger()
    @Volatile private var ultimaAtividade = 0L
    private var inicio = 0L

    @SuppressLint("SetJavaScriptEnabled")
    private fun navegador(): WebView = web ?: WebView(appCtx).also { w ->
        w.settings.javaScriptEnabled = true
        w.settings.domStorageEnabled = true
        w.webViewClient = Cliente()
        web = w
    }

    fun gravar(caminho: String, fim: (Boolean) -> Unit) {
        geracao++
        pagina = caminho
        aoTerminar = fim
        recursos.clear()
        principalOk = false
        carregou = false
        pendentes.set(0)
        inicio = SystemClock.elapsedRealtime()
        ultimaAtividade = inicio
        navegador().loadUrl(base + caminho)
        principal.postDelayed(::conferir, 400)
    }

    /** Terminou quando a página carregou e ficou um tempo sem pedir mais nada. */
    private fun conferir() {
        val fim = aoTerminar ?: return
        val agora = SystemClock.elapsedRealtime()
        val quieta = carregou && pendentes.get() == 0 && agora - ultimaAtividade > 1500
        if (!quieta && agora - inicio < LIMITE_MS) {
            principal.postDelayed(::conferir, 300)
            return
        }
        aoTerminar = null
        geracao++
        web?.stopLoading()
        web?.loadUrl("about:blank")   // para o JS da página (o socket fica tentando reconectar)
        val ok = principalOk
        if (ok) acervo.concluirPagina(pagina, recursos.toList(), System.currentTimeMillis())
        fim(ok)
    }

    fun encerrar() {
        aoTerminar = null
        web?.destroy()
        web = null
    }

    private inner class Cliente : WebViewClient() {
        override fun onPageFinished(view: WebView, url: String?) {
            if (url != null && url.startsWith(base)) carregou = true
        }

        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
            val url = request.url.toString()
            if (request.method != "GET" || !url.startsWith("http")) return null
            val daIgreja = url.startsWith(base)
            // Ao vivo (socket) não tem como salvar; site de fora (YouTube…) não precisa
            if (daIgreja && request.url.path.orEmpty().startsWith("/socket.io")) return vazio(404)
            if (!daIgreja && request.url.host !in DE_FORA) return vazio(204)

            val minha = geracao
            pendentes.incrementAndGet()
            ultimaAtividade = SystemClock.elapsedRealtime()
            try {
                val r = baixar(url, request.requestHeaders) ?: return null
                if (minha != geracao) return r.resposta()
                val chave = acervo.chave(url, base)
                if (r.codigo == 200) {
                    acervo.guardar(chave, r.mime, r.charset, r.corpo)
                    recursos += chave
                    if (chave == pagina) principalOk = true
                }
                return r.resposta()
            } catch (e: Exception) {
                return null
            } finally {
                pendentes.decrementAndGet()
                ultimaAtividade = SystemClock.elapsedRealtime()
            }
        }
    }

    private class Baixado(val codigo: Int, val motivo: String, val mime: String, val charset: String?, val corpo: ByteArray) {
        fun resposta() = WebResourceResponse(mime, charset, codigo, motivo.ifBlank { "OK" },
            mapOf("Access-Control-Allow-Origin" to "*"), ByteArrayInputStream(corpo))
    }

    private fun baixar(url: String, cabecalhos: Map<String, String>): Baixado? {
        val con = URL(url).openConnection() as HttpURLConnection
        con.connectTimeout = 10_000
        con.readTimeout = 20_000
        // Accept-Encoding fica de fora: assim o Android já entrega o conteúdo descompactado
        for ((k, v) in cabecalhos) if (!k.equals("Accept-Encoding", true)) con.setRequestProperty(k, v)
        CookieManager.getInstance().getCookie(url)?.let { con.setRequestProperty("Cookie", it) }
        try {
            val codigo = con.responseCode
            val corpo = (if (codigo < 400) con.inputStream else con.errorStream)?.use { it.readBytes() } ?: ByteArray(0)
            val tipo = con.contentType ?: "application/octet-stream"
            val mime = tipo.substringBefore(';').trim().ifBlank { "application/octet-stream" }
            val charset = Regex("""charset=([^;]+)""", RegexOption.IGNORE_CASE).find(tipo)?.groupValues?.get(1)?.trim()
                ?: if (mime.startsWith("text/") || mime.contains("javascript") || mime.contains("json")) "utf-8" else null
            return Baixado(codigo, con.responseMessage ?: "", mime, charset, corpo)
        } finally {
            con.disconnect()
        }
    }

    private fun vazio(codigo: Int) = WebResourceResponse("text/plain", "utf-8", codigo,
        if (codigo == 204) "No Content" else "Not Found", emptyMap(), ByteArrayInputStream(ByteArray(0)))

    companion object {
        private const val LIMITE_MS = 25_000L
        /** Sites de fora de que as páginas podem precisar (fontes, bibliotecas). */
        private val DE_FORA = setOf("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com", "unpkg.com", "code.jquery.com")
    }
}
