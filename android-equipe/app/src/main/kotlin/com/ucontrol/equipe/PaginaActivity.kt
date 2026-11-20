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
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.view.View
import android.widget.Button
import android.widget.TextView
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
 * - sem conexão, uma página de erro com "Tentar de novo" — ou, se a página
 *   está salva no celular, a versão salva (modo salvo: os arquivos vêm do
 *   Acervo em vez da rede);
 * - aberta de uma playlist, a barra "anterior / próxima" embaixo.
 */
class PaginaActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var base: String
    private var escolhaDeArquivo: ValueCallback<Array<Uri>>? = null
    private lateinit var banco: Banco
    private lateinit var acervo: Acervo
    /** Entregar as páginas salvas no celular em vez de buscar na rede. */
    @Volatile private var modoSalvo = false
    private var playlist = 0L
    private var posicao = 0
    private var daPlaylist: List<MusicaSalva> = emptyList()

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

        banco = Banco.de(this)
        acervo = Acervo(banco)
        modoSalvo = intent.getBooleanExtra(EXTRA_SALVO, false)
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

        playlist = intent.getLongExtra(EXTRA_PLAYLIST, 0)
        posicao = savedInstanceState?.getInt(EXTRA_POSICAO) ?: intent.getIntExtra(EXTRA_POSICAO, 0)
        if (playlist != 0L) prepararPlaylist()

        if (savedInstanceState != null) web.restoreState(savedInstanceState)
        else web.loadUrl(base + (intent.getStringExtra(EXTRA_CAMINHO) ?: "/"))
    }

    private fun prepararPlaylist() {
        daPlaylist = banco.musicasDaPlaylist(playlist)
        if (daPlaylist.isEmpty()) return
        findViewById<View>(R.id.barraPlaylist).visibility = View.VISIBLE
        findViewById<Button>(R.id.btnAnterior).setOnClickListener { irPara(posicao - 1) }
        findViewById<Button>(R.id.btnProxima).setOnClickListener { irPara(posicao + 1) }
        mostrarPosicao()
    }

    private fun irPara(p: Int) {
        if (p !in daPlaylist.indices) return
        posicao = p
        mostrarPosicao()
        web.loadUrl("$base/view/${daPlaylist[p].id}")
    }

    private fun mostrarPosicao() {
        val nome = banco.nomeDaPlaylist(playlist) ?: ""
        findViewById<TextView>(R.id.posicao).text =
            getString(R.string.posicao_playlist, posicao + 1, daPlaylist.size, nome)
        findViewById<Button>(R.id.btnAnterior).isEnabled = posicao > 0
        findViewById<Button>(R.id.btnProxima).isEnabled = posicao < daPlaylist.size - 1
    }

    /** No modo salvo, a faixa de cima diz de quando é a versão que está na tela. */
    private fun mostrarAviso(url: String?) {
        val aviso = findViewById<TextView>(R.id.aviso)
        val salvaEm = if (modoSalvo && url != null && url.startsWith(base)) banco.paginaSalvaEm(acervo.chave(url, base)) else null
        if (salvaEm == null) {
            aviso.visibility = View.GONE
        } else {
            aviso.text = getString(R.string.versao_salva, Datas.quando(salvaEm))
            aviso.visibility = View.VISIBLE
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
        outState.putInt(EXTRA_POSICAO, posicao)
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
            mostrarAviso(url)
        }

        /** Modo salvo: o que está no celular vem do Acervo; o resto tenta a rede. */
        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
            if (!modoSalvo || request.method != "GET") return null
            return acervo.abrir(acervo.chave(request.url.toString(), base))
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (!request.isForMainFrame) return
            val tentar = request.url.toString()
            // Sem conexão, mas a página está salva: mostra a versão do celular
            if (!modoSalvo && tentar.startsWith(base) && banco.paginaSalvaEm(acervo.chave(tentar, base)) != null) {
                modoSalvo = true
                Toast.makeText(this@PaginaActivity, R.string.sem_conexao_usando_salva, Toast.LENGTH_LONG).show()
                view.loadUrl(tentar)
                return
            }
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

        /** Botão "+ Playlist" que a ponte.js põe na página da cifra. */
        @JavascriptInterface
        fun paraPlaylist(id: Int, titulo: String, autor: String) = runOnUiThread {
            Dialogos.playlists(this@PaginaActivity, MusicaSalva(id, titulo, autor))
        }
    }

    companion object {
        const val EXTRA_CAMINHO = "caminho"
        /** Abrir do que está salvo no celular (cultos e playlists). */
        const val EXTRA_SALVO = "salvo"
        const val EXTRA_PLAYLIST = "playlist"
        const val EXTRA_POSICAO = "posicao"
    }
}
