package com.ucontrol.equipe

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.io.File

/** Um culto guardado no celular (vem de /api/app/salvar). */
data class CultoSalvo(val chave: String, val data: String, val titulo: String, val dirigente: String, val salvoEm: Long)

/** Uma música guardada (de um culto ou de uma playlist). */
data class MusicaSalva(val id: Int, val titulo: String, val autor: String)

data class Playlist(val id: Long, val nome: String, val quantas: Int)

/**
 * O banco SQLite do app: o que fica guardado no celular para tocar sem internet.
 * Um banco por igreja (pelo `id` do /api/identidade), para trocar de igreja não
 * misturar as cifras.
 *
 * - recursos: cada arquivo baixado (a página da cifra, o CSS, o JS, a fonte…),
 *   pelo endereço; o conteúdo fica em arquivo na pasta do banco (Acervo).
 * - paginas / pagina_recursos: uma página salva e tudo de que ela precisa.
 * - cultos / culto_musicas: os cultos guardados e as músicas de cada um.
 * - musicas: título e versão das músicas guardadas.
 * - playlists / playlist_musicas: as listas de cada pessoa (só no celular dela).
 */
class Banco private constructor(ctx: Context, val pasta: File) :
    SQLiteOpenHelper(ctx, File(pasta, "salvos.db").absolutePath, null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE recursos (chave TEXT PRIMARY KEY, mime TEXT, charset TEXT, arquivo TEXT NOT NULL, salvo_em INTEGER NOT NULL)")
        db.execSQL("CREATE TABLE paginas (chave TEXT PRIMARY KEY, salva_em INTEGER NOT NULL)")
        db.execSQL("CREATE TABLE pagina_recursos (pagina TEXT NOT NULL, recurso TEXT NOT NULL, PRIMARY KEY (pagina, recurso))")
        db.execSQL("CREATE TABLE cultos (chave TEXT PRIMARY KEY, data TEXT NOT NULL, titulo TEXT, dirigente TEXT, versao TEXT, salvo_em INTEGER NOT NULL DEFAULT 0)")
        db.execSQL("CREATE TABLE culto_musicas (culto TEXT NOT NULL, musica INTEGER NOT NULL, posicao INTEGER NOT NULL, PRIMARY KEY (culto, musica))")
        db.execSQL("CREATE TABLE musicas (id INTEGER PRIMARY KEY, titulo TEXT, autor TEXT, versao TEXT)")
        db.execSQL("CREATE TABLE playlists (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, criada_em INTEGER NOT NULL)")
        db.execSQL("CREATE TABLE playlist_musicas (playlist INTEGER NOT NULL, musica INTEGER NOT NULL, posicao INTEGER NOT NULL, PRIMARY KEY (playlist, musica))")
        db.execSQL("CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT)")
    }

    override fun onUpgrade(db: SQLiteDatabase, antiga: Int, nova: Int) {}

    /** Atualiza a linha se existe, senão cria — sem mexer nas outras colunas
     *  (o "ON CONFLICT DO UPDATE" do SQLite só existe a partir do Android 11). */
    private fun gravar(db: SQLiteDatabase, tabela: String, valores: ContentValues, onde: String, chave: String) {
        if (db.update(tabela, valores, onde, arrayOf(chave)) == 0) db.insert(tabela, null, valores)
    }

    // ------------------------------------------------------------ meta ---

    fun meta(chave: String): String? =
        readableDatabase.rawQuery("SELECT valor FROM meta WHERE chave = ?", arrayOf(chave)).use {
            if (it.moveToFirst()) it.getString(0) else null
        }

    fun meta(chave: String, valor: String) {
        writableDatabase.insertWithOnConflict("meta", null,
            ContentValues().apply { put("chave", chave); put("valor", valor) }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    // ---------------------------------------------------------- páginas ---

    fun paginaSalvaEm(chave: String): Long? =
        readableDatabase.rawQuery("SELECT salva_em FROM paginas WHERE chave = ?", arrayOf(chave)).use {
            if (it.moveToFirst()) it.getLong(0) else null
        }

    // ----------------------------------------------------------- cultos ---

    fun cultos(): List<CultoSalvo> =
        readableDatabase.rawQuery("SELECT chave, data, titulo, dirigente, salvo_em FROM cultos ORDER BY chave DESC", null).use {
            val lista = mutableListOf<CultoSalvo>()
            while (it.moveToNext()) lista += CultoSalvo(it.getString(0), it.getString(1), it.getString(2) ?: "",
                it.getString(3) ?: "", it.getLong(4))
            lista
        }

    fun versaoDoCulto(chave: String): String? =
        readableDatabase.rawQuery("SELECT versao FROM cultos WHERE chave = ?", arrayOf(chave)).use {
            if (it.moveToFirst()) it.getString(0) else null
        }

    /** Grava o culto e as músicas dele. `versao` só entra depois que as páginas foram salvas. */
    fun guardarCulto(c: CultoSalvo, musicas: List<MusicaSalva>) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            gravar(db, "cultos", ContentValues().apply {
                put("chave", c.chave); put("data", c.data); put("titulo", c.titulo); put("dirigente", c.dirigente)
            }, "chave = ?", c.chave)
            db.delete("culto_musicas", "culto = ?", arrayOf(c.chave))
            musicas.forEachIndexed { i, m ->
                guardarMusica(db, m)
                db.insert("culto_musicas", null, ContentValues().apply {
                    put("culto", c.chave); put("musica", m.id); put("posicao", i)
                })
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun cultoSalvo(chave: String, versao: String, quando: Long) {
        writableDatabase.execSQL("UPDATE cultos SET versao = ?, salvo_em = ? WHERE chave = ?", arrayOf(versao, quando, chave))
    }

    fun apagarCulto(chave: String) {
        val db = writableDatabase
        db.delete("culto_musicas", "culto = ?", arrayOf(chave))
        db.delete("cultos", "chave = ?", arrayOf(chave))
    }

    fun musicasDoCulto(chave: String): List<Int> =
        readableDatabase.rawQuery("SELECT musica FROM culto_musicas WHERE culto = ? ORDER BY posicao", arrayOf(chave)).use {
            val l = mutableListOf<Int>(); while (it.moveToNext()) l += it.getInt(0); l
        }

    // ---------------------------------------------------------- músicas ---

    private fun guardarMusica(db: SQLiteDatabase, m: MusicaSalva) {
        gravar(db, "musicas", ContentValues().apply {
            put("id", m.id); put("titulo", m.titulo); put("autor", m.autor)
        }, "id = ?", m.id.toString())
    }

    fun guardarMusica(m: MusicaSalva) = guardarMusica(writableDatabase, m)

    fun versaoDaMusica(id: Int): String? =
        readableDatabase.rawQuery("SELECT versao FROM musicas WHERE id = ?", arrayOf(id.toString())).use {
            if (it.moveToFirst()) it.getString(0) else null
        }

    fun musicaSalva(id: Int, versao: String) {
        writableDatabase.execSQL("UPDATE musicas SET versao = ? WHERE id = ?", arrayOf(versao, id))
    }

    /** Sem internet, a busca da playlist procura entre as músicas já guardadas. */
    fun buscarMusicas(q: String): List<MusicaSalva> =
        readableDatabase.rawQuery("SELECT id, titulo, autor FROM musicas WHERE titulo LIKE ? OR autor LIKE ? ORDER BY titulo LIMIT 30",
            arrayOf("%$q%", "%$q%")).use {
            val l = mutableListOf<MusicaSalva>()
            while (it.moveToNext()) l += MusicaSalva(it.getInt(0), it.getString(1) ?: "", it.getString(2) ?: "")
            l
        }

    // -------------------------------------------------------- playlists ---

    fun playlists(): List<Playlist> =
        readableDatabase.rawQuery("SELECT p.id, p.nome, COUNT(pm.musica) FROM playlists p " +
            "LEFT JOIN playlist_musicas pm ON pm.playlist = p.id GROUP BY p.id ORDER BY p.nome COLLATE NOCASE", null).use {
            val l = mutableListOf<Playlist>()
            while (it.moveToNext()) l += Playlist(it.getLong(0), it.getString(1), it.getInt(2))
            l
        }

    fun criarPlaylist(nome: String): Long =
        writableDatabase.insert("playlists", null, ContentValues().apply {
            put("nome", nome.trim()); put("criada_em", System.currentTimeMillis())
        })

    fun renomearPlaylist(id: Long, nome: String) {
        writableDatabase.execSQL("UPDATE playlists SET nome = ? WHERE id = ?", arrayOf(nome.trim(), id))
    }

    fun apagarPlaylist(id: Long) {
        writableDatabase.delete("playlist_musicas", "playlist = ?", arrayOf(id.toString()))
        writableDatabase.delete("playlists", "id = ?", arrayOf(id.toString()))
    }

    fun nomeDaPlaylist(id: Long): String? =
        readableDatabase.rawQuery("SELECT nome FROM playlists WHERE id = ?", arrayOf(id.toString())).use {
            if (it.moveToFirst()) it.getString(0) else null
        }

    fun musicasDaPlaylist(id: Long): List<MusicaSalva> =
        readableDatabase.rawQuery("SELECT m.id, m.titulo, m.autor FROM playlist_musicas pm JOIN musicas m ON m.id = pm.musica " +
            "WHERE pm.playlist = ? ORDER BY pm.posicao", arrayOf(id.toString())).use {
            val l = mutableListOf<MusicaSalva>()
            while (it.moveToNext()) l += MusicaSalva(it.getInt(0), it.getString(1) ?: "", it.getString(2) ?: "")
            l
        }

    /** Em quais playlists a música está (para marcar no diálogo "Salvar na playlist"). */
    fun playlistsDaMusica(musica: Int): Set<Long> =
        readableDatabase.rawQuery("SELECT playlist FROM playlist_musicas WHERE musica = ?", arrayOf(musica.toString())).use {
            val s = mutableSetOf<Long>(); while (it.moveToNext()) s += it.getLong(0); s
        }

    fun porNaPlaylist(playlist: Long, m: MusicaSalva) {
        val db = writableDatabase
        guardarMusica(db, m)
        val fim = db.rawQuery("SELECT COALESCE(MAX(posicao) + 1, 0) FROM playlist_musicas WHERE playlist = ?",
            arrayOf(playlist.toString())).use { it.moveToFirst(); it.getInt(0) }
        db.insertWithOnConflict("playlist_musicas", null, ContentValues().apply {
            put("playlist", playlist); put("musica", m.id); put("posicao", fim)
        }, SQLiteDatabase.CONFLICT_IGNORE)
    }

    fun tirarDaPlaylist(playlist: Long, musica: Int) {
        writableDatabase.delete("playlist_musicas", "playlist = ? AND musica = ?", arrayOf(playlist.toString(), musica.toString()))
    }

    fun reordenarPlaylist(playlist: Long, ids: List<Int>) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            ids.forEachIndexed { i, id ->
                db.execSQL("UPDATE playlist_musicas SET posicao = ? WHERE playlist = ? AND musica = ?", arrayOf(i, playlist, id))
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    /** Músicas que estão em alguma playlist (o que a sincronia mantém em dia). */
    fun musicasDasPlaylists(): List<Int> =
        readableDatabase.rawQuery("SELECT DISTINCT musica FROM playlist_musicas", null).use {
            val l = mutableListOf<Int>(); while (it.moveToNext()) l += it.getInt(0); l
        }

    companion object {
        private var aberto: Banco? = null
        private var deQuem: String? = null

        /** O banco da igreja salva agora. */
        @Synchronized
        fun de(ctx: Context): Banco {
            val igreja = Servidor.salvo(ctx)
            val quem = igreja?.id?.ifBlank { null } ?: igreja?.endereco?.hashCode()?.toUInt()?.toString(16) ?: "nenhuma"
            aberto?.let { if (deQuem == quem) return it else it.close() }
            val pasta = File(ctx.applicationContext.filesDir, "salvos/$quem").apply { mkdirs() }
            return Banco(ctx.applicationContext, pasta).also { aberto = it; deQuem = quem }
        }
    }
}
