package com.ucontrol.equipe

import android.app.Activity
import android.text.InputType
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.Toast
import androidx.appcompat.app.AlertDialog

/** Diálogos usados em mais de uma tela. */
object Dialogos {

    /** Pede um nome (playlist nova, renomear). */
    fun nome(a: Activity, titulo: Int, atual: String = "", ok: (String) -> Unit) {
        val campo = EditText(a).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            setSingleLine(true)
            setText(atual)
            setSelectAllOnFocus(true)
            hint = a.getString(R.string.playlist_dica_nome)
        }
        val moldura = FrameLayout(a).apply {
            val m = (20 * a.resources.displayMetrics.density).toInt()
            setPadding(m, m / 2, m, 0)
            addView(campo)
        }
        AlertDialog.Builder(a)
            .setTitle(titulo)
            .setView(moldura)
            .setPositiveButton(R.string.salvar) { _, _ ->
                val nome = campo.text.toString().trim()
                if (nome.isNotEmpty()) ok(nome)
            }
            .setNegativeButton(R.string.cancelar, null)
            .show()
        campo.requestFocus()
    }

    /**
     * "Salvar na playlist": marca em quais listas a música fica. A música fica
     * guardada no celular (a sincronia baixa a página dela).
     */
    fun playlists(a: Activity, musica: MusicaSalva) {
        val banco = Banco.de(a)
        val listas = banco.playlists()
        if (listas.isEmpty()) {
            nome(a, R.string.playlist_nova) { nome ->
                banco.porNaPlaylist(banco.criarPlaylist(nome), musica)
                salvou(a, a.getString(R.string.playlist_salva_em, nome))
            }
            return
        }
        val dentro = banco.playlistsDaMusica(musica.id)
        val marcadas = BooleanArray(listas.size) { listas[it].id in dentro }
        AlertDialog.Builder(a)
            .setTitle(a.getString(R.string.playlist_salvar_titulo, musica.titulo))
            .setMultiChoiceItems(listas.map { it.nome }.toTypedArray(), marcadas) { _, i, sim -> marcadas[i] = sim }
            .setPositiveButton(R.string.salvar) { _, _ ->
                listas.forEachIndexed { i, p ->
                    if (marcadas[i] && p.id !in dentro) banco.porNaPlaylist(p.id, musica)
                    if (!marcadas[i] && p.id in dentro) banco.tirarDaPlaylist(p.id, musica.id)
                }
                val nomes = listas.filterIndexed { i, _ -> marcadas[i] }.joinToString(", ") { it.nome }
                salvou(a, if (nomes.isEmpty()) a.getString(R.string.playlist_tirada) else a.getString(R.string.playlist_salva_em, nomes))
            }
            .setNeutralButton(R.string.playlist_nova) { _, _ ->
                nome(a, R.string.playlist_nova) { nome ->
                    banco.porNaPlaylist(banco.criarPlaylist(nome), musica)
                    salvou(a, a.getString(R.string.playlist_salva_em, nome))
                }
            }
            .setNegativeButton(R.string.cancelar, null)
            .show()
    }

    private fun salvou(a: Activity, texto: String) {
        Toast.makeText(a, texto, Toast.LENGTH_SHORT).show()
        Sincronia.sincronizar(a, agora = true)
    }
}
