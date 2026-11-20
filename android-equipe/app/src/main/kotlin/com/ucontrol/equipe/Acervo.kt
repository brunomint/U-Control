package com.ucontrol.equipe

import android.content.ContentValues
import android.database.sqlite.SQLiteDatabase
import android.webkit.WebResourceResponse
import java.io.ByteArrayInputStream
import java.io.File
import java.security.MessageDigest

/**
 * Os arquivos das páginas salvas. O banco (tabela recursos) diz qual endereço
 * é qual arquivo; o conteúdo fica em `<pasta do banco>/arquivos/<sha1>` — o
 * mesmo CSS usado por 50 cifras é um arquivo só.
 *
 * A chave de um endereço da igreja é só o caminho ("/view/12?order=2026-11-22"),
 * para o salvo valer tanto pelo Wi-Fi (http://192.168…) quanto pelo site.
 */
class Acervo(private val banco: Banco) {

    private val pasta = File(banco.pasta, "arquivos").apply { mkdirs() }

    fun chave(url: String, base: String): String =
        if (url.startsWith(base)) url.substring(base.length).ifEmpty { "/" } else url

    /** Guarda um arquivo baixado. Ainda não pertence a nenhuma página: ver [concluirPagina]. */
    fun guardar(chave: String, mime: String, charset: String?, conteudo: ByteArray) {
        val nome = sha1(conteudo)
        val arquivo = File(pasta, nome)
        if (!arquivo.exists()) {
            val tmp = File(pasta, "$nome.tmp")
            tmp.writeBytes(conteudo)
            tmp.renameTo(arquivo)
        }
        banco.writableDatabase.insertWithOnConflict("recursos", null, ContentValues().apply {
            put("chave", chave); put("mime", mime); put("charset", charset); put("arquivo", nome)
            put("salvo_em", System.currentTimeMillis())
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    /** A página e tudo que ela carregou foram salvos: troca a versão antiga pela nova de uma vez. */
    fun concluirPagina(pagina: String, recursos: Collection<String>, quando: Long) {
        val db = banco.writableDatabase
        db.beginTransaction()
        try {
            db.delete("pagina_recursos", "pagina = ?", arrayOf(pagina))
            for (r in recursos.toSet() + pagina) {
                db.insert("pagina_recursos", null, ContentValues().apply { put("pagina", pagina); put("recurso", r) })
            }
            db.insertWithOnConflict("paginas", null, ContentValues().apply {
                put("chave", pagina); put("salva_em", quando)
            }, SQLiteDatabase.CONFLICT_REPLACE)
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    /** O arquivo salvo para esse endereço, pronto para o WebView; null se não tem. */
    fun abrir(chave: String): WebResourceResponse? {
        val (mime, charset, nome) = banco.readableDatabase.rawQuery(
            "SELECT mime, charset, arquivo FROM recursos WHERE chave = ?", arrayOf(chave)
        ).use {
            if (!it.moveToFirst()) return null
            Triple(it.getString(0) ?: "application/octet-stream", it.getString(1), it.getString(2))
        }
        val arquivo = File(pasta, nome)
        if (!arquivo.exists()) return null
        return WebResourceResponse(mime, charset, 200, "OK",
            mapOf("Access-Control-Allow-Origin" to "*", "Cache-Control" to "no-store"),
            ByteArrayInputStream(arquivo.readBytes()))
    }

    /**
     * Apaga o que nenhuma página salva usa mais: páginas fora de `manter`,
     * endereços sem página e arquivos sem endereço.
     */
    fun limpar(manter: Set<String>) {
        val db = banco.writableDatabase
        db.beginTransaction()
        try {
            val todas = db.rawQuery("SELECT chave FROM paginas", null).use {
                val l = mutableListOf<String>(); while (it.moveToNext()) l += it.getString(0); l
            }
            for (p in todas) if (p !in manter) {
                db.delete("pagina_recursos", "pagina = ?", arrayOf(p))
                db.delete("paginas", "chave = ?", arrayOf(p))
            }
            db.execSQL("DELETE FROM recursos WHERE chave NOT IN (SELECT recurso FROM pagina_recursos)")
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        val usados = db.rawQuery("SELECT DISTINCT arquivo FROM recursos", null).use {
            val s = mutableSetOf<String>(); while (it.moveToNext()) s += it.getString(0); s
        }
        pasta.listFiles()?.forEach { if (it.name !in usados) it.delete() }
    }

    /** Quanto o salvo ocupa no celular, em bytes. */
    fun tamanho(): Long = pasta.listFiles()?.sumOf { it.length() } ?: 0L

    private fun sha1(b: ByteArray): String =
        MessageDigest.getInstance("SHA-1").digest(b).joinToString("") { "%02x".format(it) }
}
