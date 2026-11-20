package com.ucontrol.equipe

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.util.TypedValue
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.ItemTouchHelper
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.json.JSONArray
import java.net.URLEncoder
import kotlin.concurrent.thread

/**
 * Uma playlist: tocar em sequência, arrastar (≡) para mudar a ordem, deslizar
 * para o lado para tirar, "Adicionar música" para buscar no U-Control.
 */
class PlaylistActivity : AppCompatActivity() {

    private var id = 0L
    private lateinit var banco: Banco
    private val musicas = mutableListOf<MusicaSalva>()
    private lateinit var adaptador: Adaptador
    private lateinit var vazio: TextView
    private lateinit var arrastar: ItemTouchHelper

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_playlist)
        respeitarBarras(findViewById(android.R.id.content))
        id = intent.getLongExtra(EXTRA_ID, 0)
        banco = Banco.de(this)
        vazio = findViewById(R.id.vazio)

        val rv = findViewById<RecyclerView>(R.id.musicas)
        adaptador = Adaptador()
        rv.layoutManager = LinearLayoutManager(this)
        rv.adapter = adaptador
        arrastar = ItemTouchHelper(Gestos())
        arrastar.attachToRecyclerView(rv)

        findViewById<View>(R.id.btnOpcoes).setOnClickListener { opcoes() }
        findViewById<View>(R.id.nome).setOnClickListener { opcoes() }
        findViewById<Button>(R.id.btnAdicionar).setOnClickListener { buscar() }
        findViewById<Button>(R.id.btnTocar).setOnClickListener { if (musicas.isNotEmpty()) abrir(0) }
    }

    override fun onResume() {
        super.onResume()
        recarregar()
    }

    private fun recarregar() {
        val nome = banco.nomeDaPlaylist(id) ?: return finish()
        findViewById<TextView>(R.id.nome).text = nome
        musicas.clear()
        musicas += banco.musicasDaPlaylist(id)
        adaptador.notifyDataSetChanged()
        vazio.visibility = if (musicas.isEmpty()) View.VISIBLE else View.GONE
        findViewById<Button>(R.id.btnTocar).isEnabled = musicas.isNotEmpty()
    }

    private fun abrir(posicao: Int) {
        startActivity(Intent(this, PaginaActivity::class.java)
            .putExtra(PaginaActivity.EXTRA_CAMINHO, "/view/${musicas[posicao].id}")
            .putExtra(PaginaActivity.EXTRA_SALVO, true)
            .putExtra(PaginaActivity.EXTRA_PLAYLIST, id)
            .putExtra(PaginaActivity.EXTRA_POSICAO, posicao))
    }

    private fun opcoes() {
        AlertDialog.Builder(this)
            .setItems(arrayOf(getString(R.string.renomear), getString(R.string.playlist_apagar))) { _, i ->
                if (i == 0) {
                    Dialogos.nome(this, R.string.renomear, banco.nomeDaPlaylist(id) ?: "") {
                        banco.renomearPlaylist(id, it); recarregar()
                    }
                } else {
                    AlertDialog.Builder(this)
                        .setMessage(getString(R.string.playlist_apagar_pergunta, banco.nomeDaPlaylist(id)))
                        .setPositiveButton(R.string.apagar) { _, _ -> banco.apagarPlaylist(id); finish() }
                        .setNegativeButton(R.string.cancelar, null)
                        .show()
                }
            }
            .show()
    }

    /** Busca no U-Control (precisa de conexão); sem conexão, entre as músicas já salvas. */
    private fun buscar() {
        val d = resources.displayMetrics.density
        val campo = EditText(this).apply {
            hint = getString(R.string.buscar_dica)
            setSingleLine(true)
        }
        val aviso = TextView(this).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setPadding(0, (6 * d).toInt(), 0, (6 * d).toInt())
        }
        val achadas = mutableListOf<MusicaSalva>()
        val resultados = object : ArrayAdapter<MusicaSalva>(this, android.R.layout.simple_list_item_2, android.R.id.text1, achadas) {
            override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                val v = super.getView(position, convertView, parent)
                val m = getItem(position)!!
                v.findViewById<TextView>(android.R.id.text1).text = m.titulo
                v.findViewById<TextView>(android.R.id.text2).text = m.autor
                return v
            }
        }
        val listaView = ListView(this).apply {
            adapter = resultados
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, (320 * d).toInt())
        }
        val caixa = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((20 * d).toInt(), (8 * d).toInt(), (20 * d).toInt(), 0)
            addView(campo); addView(aviso); addView(listaView)
        }
        val dialogo = AlertDialog.Builder(this)
            .setTitle(R.string.adicionar_musica)
            .setView(caixa)
            .setNegativeButton(R.string.fechar, null)
            .show()

        val base = Servidor.salvo(this)?.endereco ?: return
        val espera = Handler(Looper.getMainLooper())
        var pedido = 0
        val procurar = Runnable {
            val q = campo.text.toString().trim()
            val meu = ++pedido
            if (q.length < 2) { achadas.clear(); resultados.notifyDataSetChanged(); aviso.text = ""; return@Runnable }
            aviso.setText(R.string.buscando)
            thread {
                val online = Servidor.pegar("$base/api/songs/search?q=${URLEncoder.encode(q, "UTF-8")}", 6000)
                val r = online?.let { txt ->
                    runCatching {
                        val a = JSONArray(txt)
                        (0 until a.length()).map { i ->
                            val o = a.getJSONObject(i); MusicaSalva(o.getInt("id"), o.optString("title"), o.optString("author"))
                        }
                    }.getOrNull()
                } ?: banco.buscarMusicas(q)
                runOnUiThread {
                    if (meu != pedido) return@runOnUiThread
                    achadas.clear(); achadas += r
                    resultados.notifyDataSetChanged()
                    aviso.text = when {
                        online == null -> getString(R.string.buscar_sem_conexao)
                        r.isEmpty() -> getString(R.string.buscar_nada)
                        else -> ""
                    }
                }
            }
        }
        campo.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: Editable?) {
                espera.removeCallbacks(procurar); espera.postDelayed(procurar, 400)
            }
        })
        listaView.setOnItemClickListener { _, _, i, _ ->
            val m = achadas[i]
            if (musicas.any { it.id == m.id }) {
                Toast.makeText(this, getString(R.string.ja_esta, m.titulo), Toast.LENGTH_SHORT).show()
            } else {
                banco.porNaPlaylist(id, m)
                recarregar()
                Sincronia.sincronizar(this, agora = true)
                Toast.makeText(this, getString(R.string.adicionada, m.titulo), Toast.LENGTH_SHORT).show()
            }
        }
        campo.requestFocus()
        dialogo.window?.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE)
    }

    private inner class Gestos : ItemTouchHelper.SimpleCallback(ItemTouchHelper.UP or ItemTouchHelper.DOWN,
        ItemTouchHelper.LEFT or ItemTouchHelper.RIGHT) {
        override fun isLongPressDragEnabled() = true

        override fun onMove(rv: RecyclerView, de: RecyclerView.ViewHolder, para: RecyclerView.ViewHolder): Boolean {
            val a = de.bindingAdapterPosition
            val b = para.bindingAdapterPosition
            musicas.add(b, musicas.removeAt(a))
            adaptador.notifyItemMoved(a, b)
            return true
        }

        override fun clearView(rv: RecyclerView, vh: RecyclerView.ViewHolder) {
            super.clearView(rv, vh)
            banco.reordenarPlaylist(id, musicas.map { it.id })
            rv.post { adaptador.notifyDataSetChanged() }   // renumera
        }

        override fun onSwiped(vh: RecyclerView.ViewHolder, direcao: Int) {
            val pos = vh.bindingAdapterPosition
            val m = musicas[pos]
            banco.tirarDaPlaylist(id, m.id)
            recarregar()
            Toast.makeText(this@PlaylistActivity, getString(R.string.tirada, m.titulo), Toast.LENGTH_SHORT).show()
        }
    }

    private inner class Linha(val v: LinearLayout, val titulo: TextView, val sub: TextView, val alca: TextView) :
        RecyclerView.ViewHolder(v)

    private inner class Adaptador : RecyclerView.Adapter<Linha>() {
        override fun getItemCount() = musicas.size

        @SuppressLint("ClickableViewAccessibility")
        override fun onCreateViewHolder(parent: ViewGroup, tipo: Int): Linha {
            val d = resources.displayMetrics.density
            val corpo = linhaDeLista(this@PlaylistActivity, "", " ")
            val textos = LinearLayout(this@PlaylistActivity).apply { orientation = LinearLayout.VERTICAL }
            val titulo = corpo.getChildAt(0) as TextView
            val sub = corpo.getChildAt(1) as TextView
            corpo.removeAllViews()
            textos.addView(titulo); textos.addView(sub)
            corpo.orientation = LinearLayout.HORIZONTAL
            corpo.addView(textos, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            val alca = TextView(this@PlaylistActivity).apply {
                text = "≡"
                setTextColor(0x99FFFFFF.toInt())
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f)
                setPadding((16 * d).toInt(), 0, 0, 0)
                contentDescription = getString(R.string.arrastar)
            }
            corpo.addView(alca)
            corpo.layoutParams = RecyclerView.LayoutParams(RecyclerView.LayoutParams.MATCH_PARENT,
                RecyclerView.LayoutParams.WRAP_CONTENT).apply { bottomMargin = (8 * d).toInt() }
            val linha = Linha(corpo, titulo, sub, alca)
            alca.setOnTouchListener { _, e ->
                if (e.actionMasked == MotionEvent.ACTION_DOWN) arrastar.startDrag(linha)
                false
            }
            return linha
        }

        override fun onBindViewHolder(h: Linha, pos: Int) {
            val m = musicas[pos]
            h.titulo.text = "${pos + 1}. ${m.titulo}"
            h.sub.text = m.autor
            h.sub.visibility = if (m.autor.isBlank()) View.GONE else View.VISIBLE
            h.v.setOnClickListener { abrir(h.bindingAdapterPosition) }
        }
    }

    companion object {
        const val EXTRA_ID = "playlist"
    }
}
