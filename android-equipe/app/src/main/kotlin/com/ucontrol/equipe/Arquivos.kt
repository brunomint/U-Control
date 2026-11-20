package com.ucontrol.equipe

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.text.Html
import android.util.Base64
import java.io.File

/** Arquivos que a página gera no próprio navegador (PDF da ordem, imagem do calendário). */
object Arquivos {

    private var ponte: String? = null

    /** assets/ponte.js: liga os downloads blob:, a impressão e a página sem conexão ao app. */
    fun ponteJs(ctx: Context): String =
        ponte ?: ctx.assets.open("ponte.js").bufferedReader().use { it.readText() }.also { ponte = it }

    /**
     * O nome que o U-Control mandou (ex.: o PDF da cifra vem como
     * `inline; filename="Hino.pdf"`). O URLUtil.guessFileName do Android só
     * lê o nome quando vem como "attachment" e devolveria "print.pdf".
     */
    fun nomeDoArquivo(disposicao: String?): String? {
        if (disposicao.isNullOrBlank()) return null
        val utf8 = Regex("""filename\*\s*=\s*UTF-8''([^;]+)""", RegexOption.IGNORE_CASE).find(disposicao)
        if (utf8 != null) return java.net.URLDecoder.decode(utf8.groupValues[1].trim(), "UTF-8")
        val simples = Regex("""filename\s*=\s*"?([^";]+)"?""", RegexOption.IGNORE_CASE).find(disposicao)
        return simples?.groupValues?.get(1)?.trim()?.ifBlank { null }
    }

    /** Grava "data:<tipo>;base64,<conteúdo>" na pasta Downloads. Devolve onde ficou, ou null. */
    fun salvarDataUrl(ctx: Context, dataUrl: String, nomePedido: String): String? {
        val virgula = dataUrl.indexOf(',')
        if (!dataUrl.startsWith("data:") || virgula < 0) return null
        val cabecalho = dataUrl.substring(5, virgula)
        val mime = cabecalho.substringBefore(';').ifBlank { "application/octet-stream" }
        val bytes = try {
            Base64.decode(dataUrl.substring(virgula + 1), Base64.DEFAULT)
        } catch (e: IllegalArgumentException) {
            return null
        }
        val nome = nomePedido.replace(Regex("""[\\/:*?"<>|]"""), "_").ifBlank { "arquivo" }

        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val valores = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, nome)
                    put(MediaStore.Downloads.MIME_TYPE, mime)
                }
                val uri = ctx.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, valores) ?: return null
                ctx.contentResolver.openOutputStream(uri)?.use { it.write(bytes) } ?: return null
                "Downloads/$nome"
            } else {
                // Android 7–9: pasta do próprio app (não pede permissão de armazenamento)
                val pasta = ctx.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS) ?: return null
                File(pasta, nome).writeBytes(bytes)
                File(pasta, nome).absolutePath
            }
        } catch (e: Exception) {
            null
        }
    }

    fun paginaSemConexao(ctx: Context, tentar: String): String {
        val igreja = Servidor.salvo(ctx)?.titulo ?: ""
        val esc = { s: String -> Html.escapeHtml(s) }
        val urlJs = tentar.replace("\\", "\\\\").replace("'", "\\'").replace("<", "\\x3c")
        return ctx.assets.open("sem_conexao.html").bufferedReader().use { it.readText() }
            .replace("{{IGREJA}}", esc(igreja))
            .replace("{{URL_JS}}", urlJs)
    }
}
