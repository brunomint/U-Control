package com.ucontrol.equipe

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.concurrent.thread

/**
 * Mantém o celular em dia com a igreja, quando tem conexão:
 * - os cultos dos próximos [DIAS] dias (ordem + cifras), de /api/app/salvar;
 * - as músicas das playlists, de /api/app/musicas.
 * Só baixa de novo o que mudou (a `versao` de cada coisa, ou o U-Control
 * atualizado). O que já está salvo nunca é apagado por falta de conexão:
 * sem internet, fica tudo como estava.
 */
object Sincronia {
    const val DIAS = 15
    private const val INTERVALO_MS = 5 * 60_000L

    private val principal = Handler(Looper.getMainLooper())
    private val ouvintes = mutableSetOf<(String) -> Unit>()
    private var rodando = false
    private var deNovo = false
    private var ultima = 0L

    var estado: String = ""
        private set

    fun ouvir(f: (String) -> Unit) { ouvintes += f; f(estado) }
    fun parar(f: (String) -> Unit) { ouvintes -= f }

    private fun avisar(texto: String) = principal.post {
        estado = texto
        ouvintes.toList().forEach { it(texto) }
    }

    /** Chamar na tela principal. `agora` = sem esperar o intervalo (ex.: música nova na playlist). */
    fun sincronizar(ctx: Context, agora: Boolean = false) {
        val app = ctx.applicationContext
        if (rodando) { if (agora) deNovo = true; return }
        if (!agora && System.currentTimeMillis() - ultima < INTERVALO_MS) return
        val igreja = Servidor.salvo(app) ?: return
        rodando = true
        ultima = System.currentTimeMillis()
        avisar(app.getString(R.string.sinc_conferindo))
        thread { planejar(app, igreja.endereco) }
    }

    private class Tarefa(val pagina: String, val grupo: String)

    /** Pergunta à igreja o que mudou e monta a lista de páginas a salvar. */
    private fun planejar(app: Context, base: String) {
        val banco = Banco.de(app)
        val json = Servidor.pegar("$base/api/app/salvar?dias=$DIAS")?.let { runCatching { JSONObject(it) }.getOrNull() }
        if (json == null) {
            terminar(app, app.getString(R.string.sinc_sem_conexao))
            return
        }
        val versaoServidor = json.optString("versao_servidor")
        val tudoDeNovo = banco.meta("versao_servidor") != versaoServidor
        val tarefas = mutableListOf<Tarefa>()
        val versoes = mutableMapOf<String, () -> Unit>()   // grupo → marca como salvo
        val agora = System.currentTimeMillis()

        // Cultos
        val vieram = mutableSetOf<String>()
        val cultos = json.optJSONArray("cultos")
        for (i in 0 until (cultos?.length() ?: 0)) {
            val c = cultos!!.getJSONObject(i)
            val chave = c.getString("chave")
            vieram += chave
            val ms = c.optJSONArray("musicas")
            val musicas = (0 until (ms?.length() ?: 0)).map {
                val m = ms!!.getJSONObject(it)
                MusicaSalva(m.getInt("id"), m.optString("titulo"), m.optString("autor"))
            }
            val versao = c.optString("versao")
            val paginas = listOf("/view?order=$chave") + musicas.map { "/view/${it.id}?order=$chave" }
            val faltaAlguma = paginas.any { banco.paginaSalvaEm(it) == null }
            banco.guardarCulto(CultoSalvo(chave, c.optString("data"), c.optString("titulo"), c.optString("dirigente"), 0), musicas)
            if (tudoDeNovo || faltaAlguma || banco.versaoDoCulto(chave) != versao) {
                paginas.forEach { tarefas += Tarefa(it, "culto:$chave") }
                versoes["culto:$chave"] = { banco.cultoSalvo(chave, versao, System.currentTimeMillis()) }
            }
        }
        // Culto futuro que saiu da agenda da igreja sai daqui também; os que já passaram ficam
        val hoje = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date(agora))
        banco.cultos().filter { it.data >= hoje && it.chave !in vieram }.forEach { banco.apagarCulto(it.chave) }

        // Músicas das playlists
        val ids = banco.musicasDasPlaylists()
        if (ids.isNotEmpty()) {
            val r = Servidor.pegar("$base/api/app/musicas?ids=${ids.joinToString(",")}")
                ?.let { runCatching { JSONObject(it) }.getOrNull() }
            val ms = r?.optJSONArray("musicas")
            for (i in 0 until (ms?.length() ?: 0)) {
                val m = ms!!.getJSONObject(i)
                val id = m.getInt("id")
                val versao = m.optString("versao")
                banco.guardarMusica(MusicaSalva(id, m.optString("titulo"), m.optString("autor")))
                val pagina = "/view/$id"
                if (tudoDeNovo || banco.paginaSalvaEm(pagina) == null || banco.versaoDaMusica(id) != versao) {
                    tarefas += Tarefa(pagina, "musica:$id")
                    versoes["musica:$id"] = { banco.musicaSalva(id, versao) }
                }
            }
            // Música que a igreja apagou: a cópia do celular fica (é para ser permanente)
        }

        principal.post { gravar(app, base, tarefas, versoes, versaoServidor) }
    }

    private fun gravar(app: Context, base: String, tarefas: List<Tarefa>, versoes: Map<String, () -> Unit>, versaoServidor: String) {
        val banco = Banco.de(app)
        val acervo = Acervo(banco)
        val gravador = Gravador(app, base, acervo)
        val falhou = mutableSetOf<String>()
        var i = 0

        fun proxima() {
            if (i >= tarefas.size) {
                gravador.encerrar()
                thread {
                    versoes.forEach { (grupo, marcar) -> if (grupo !in falhou) marcar() }
                    acervo.limpar(necessarias(banco))
                    if (falhou.isEmpty()) banco.meta("versao_servidor", versaoServidor)
                    val quando = SimpleDateFormat("dd/MM 'às' HH:mm", Locale("pt", "BR")).format(Date())
                    terminar(app, if (falhou.isEmpty()) app.getString(R.string.sinc_tudo_salvo, quando)
                                  else app.getString(R.string.sinc_faltou, falhou.size))
                }
                return
            }
            val t = tarefas[i]
            avisar(app.getString(R.string.sinc_salvando, i + 1, tarefas.size))
            gravador.gravar(t.pagina) { ok ->
                if (!ok) falhou += t.grupo
                i++
                proxima()
            }
        }
        proxima()
    }

    /** Todas as páginas que algo salvo usa: o resto pode ir embora. */
    private fun necessarias(banco: Banco): Set<String> {
        val s = mutableSetOf<String>()
        for (c in banco.cultos()) {
            s += "/view?order=${c.chave}"
            banco.musicasDoCulto(c.chave).forEach { s += "/view/$it?order=${c.chave}" }
        }
        banco.musicasDasPlaylists().forEach { s += "/view/$it" }
        return s
    }

    private fun terminar(app: Context, texto: String) {
        avisar(texto)
        principal.post {
            rodando = false
            if (deNovo) { deNovo = false; sincronizar(app, agora = true) }
        }
    }
}
