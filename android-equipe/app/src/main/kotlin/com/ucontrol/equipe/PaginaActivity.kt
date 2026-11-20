package com.ucontrol.equipe

import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.print.PrintAttributes
import android.print.PrintManager
import android.view.WindowManager
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

/**
 * Uma página do U-Control dentro do app. Além de mostrar a página:
 * - endereço de fora da igreja (YouTube, WhatsApp…) abre no app certo;
 * - escolher foto/arquivo e baixar PDF/imagem funcionam (o WebView sozinho não faz);
 * - imprimir usa a impressão do Android;
 * - a tela fica acesa nas cifras (/view), para ninguém tocar no meio da música;
 * - sem conexão, uma página de erro com "Tentar de novo".
 */
class PaginaActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var base: String
    private var escolhaDeArquivo: ValueCallback<Array<Uri>>? = null

    private val escolherArquivo = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        escolhaDeArquivo?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(r.resultCode, r.data))
        escolhaDeArquivo = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_pagina)
        respeitarBarras(findViewById(android.R.id.content))
        base = Servidor.salvo(this)?.endereco ?: return finish()

        web = findViewById(R.id.web)
        // Versão de teste: deixa inspecionar a página pelo Chrome do computador
        if (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0) {
            WebView.setWebContentsDebuggingEnabled(true)
        }
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            loadWithOverviewMode = true
            useWideViewPort = true
        }
        CookieManager.getInstance().setAcceptCookie(true)
        web.addJavascriptInterface(Ponte(), "UCApp")
        web.webViewClient = Cliente()
        web.webChromeClient = Cromo()
        web.setDownloadListener { url, userAgent, disposicao, mime, _ -> baixar(url, userAgent, disposicao, mime) }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) web.goBack() else finish()
            }
        })

        if (savedInstanceState != null) web.restoreState(savedInstanceState)
        else web.loadUrl(base + (intent.getStringExtra(EXTRA_CAMINHO) ?: "/"))
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onPause() {
        super.onPause()
        CookieManager.getInstance().flush()   // o login continua depois de fechar o app
    }

    private fun daIgreja(uri: Uri): Boolean = uri.toString().startsWith(base)

    private fun telaAcesa(url: String?) {
        val nasCifras = url != null && Uri.parse(url).path.orEmpty().startsWith("/view")
        if (nasCifras) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun baixar(url: String, userAgent: String, disposicao: String?, mime: String?) {
        // blob:/data: (PDF da ordem, imagem do calendário) a ponte.js já pegou no clique
        if (!url.startsWith("http")) return
        val nome = Arquivos.nomeDoArquivo(disposicao) ?: URLUtil.guessFileName(url, disposicao, mime)
        val pedido = DownloadManager.Request(Uri.parse(url))
            .addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url) ?: "")
            .addRequestHeader("User-Agent", userAgent)
            .setMimeType(mime)
            .setTitle(nome)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, nome)
        (getSystemService(DOWNLOAD_SERVICE) as DownloadManager).enqueue(pedido)
        Toast.makeText(this, getString(R.string.baixando, nome), Toast.LENGTH_SHORT).show()
    }

    private fun abrirFora(uri: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(this, R.string.sem_app_para_abrir, Toast.LENGTH_SHORT).show()
        }
    }

    private inner class Cliente : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            if (daIgreja(request.url)) return false
            abrirFora(request.url)
            return true
        }

        override fun onPageFinished(view: WebView, url: String?) {
            view.evaluateJavascript(Arquivos.ponteJs(this@PaginaActivity), null)
            telaAcesa(url)
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (!request.isForMainFrame) return
            val tentar = request.url.toString()
            view.loadDataWithBaseURL(null, Arquivos.paginaSemConexao(this@PaginaActivity, tentar), "text/html", "UTF-8", tentar)
        }
    }

    private inner class Cromo : WebChromeClient() {
        override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
            escolhaDeArquivo?.onReceiveValue(null)
            escolhaDeArquivo = callback
            return try {
                escolherArquivo.launch(params.createIntent())
                true
            } catch (e: ActivityNotFoundException) {
                escolhaDeArquivo = null
                false
            }
        }
    }

    /** O que a página (ponte.js e a página sem conexão) pode pedir ao app. */
    private inner class Ponte {
        @JavascriptInterface
        fun salvar(dataUrl: String, nome: String) {
            val salvo = Arquivos.salvarDataUrl(this@PaginaActivity, dataUrl, nome)
            runOnUiThread {
                val msg = if (salvo != null) getString(R.string.salvo_em, salvo) else getString(R.string.nao_salvou)
                Toast.makeText(this@PaginaActivity, msg, Toast.LENGTH_LONG).show()
            }
        }

        @JavascriptInterface
        fun imprimir() = runOnUiThread {
            val pm = getSystemService(PRINT_SERVICE) as PrintManager
            pm.print(web.title ?: "U-Control", web.createPrintDocumentAdapter(web.title ?: "U-Control"),
                PrintAttributes.Builder().build())
        }

        @JavascriptInterface
        fun tentarDeNovo(url: String) = runOnUiThread { web.loadUrl(url) }

        @JavascriptInterface
        fun voltarAoMenu() = runOnUiThread { finish() }
    }

    companion object {
        const val EXTRA_CAMINHO = "caminho"
    }
}
