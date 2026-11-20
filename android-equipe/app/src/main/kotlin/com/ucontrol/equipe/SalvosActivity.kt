package com.ucontrol.equipe

import android.content.Context
import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.format.Formatter
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * "Salvos no celular": as playlists da pessoa e os cultos guardados. Funciona
 * sem internet — tudo aqui vem do banco do app.
 */
class SalvosActivity : AppCompatActivity() {

    private lateinit var lista: LinearLayout
    private lateinit var estado: TextView
    private val ouvinte: (String) -> Unit = { texto ->
        estado.text = texto
        if (!texto.startsWith(getString(R.string.sinc_salvando_prefixo))) montar()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_salvos)
        respeitarBarras(findViewById(android.R.id.content))
        lista = findViewById(R.id.lista)
        estado = findViewById(R.id.estado)
        findViewById<Button>(R.id.btnAtualizar).setOnClickListener { Sincronia.sincronizar(this, agora = true) }
    }

    override fun onResume() {
        super.onResume()
        montar()
        Sincronia.ouvir(ouvinte)
        Sincronia.sincronizar(this)
    }

    override fun onPause() {
        super.onPause()
        Sincronia.parar(ouvinte)
    }

    private fun montar() {
        val banco = Banco.de(this)
        lista.removeAllViews()

        titulo(R.string.playlists)
        val playlists = banco.playlists()
        if (playlists.isEmpty()) texto(getString(R.string.playlists_vazio))
        for (p in playlists) {
            linha(p.nome, resources.getQuantityString(R.plurals.musicas, p.quantas, p.quantas)) {
                startActivity(Intent(this, PlaylistActivity::class.java).putExtra(PlaylistActivity.EXTRA_ID, p.id))
            }
        }
        lista.addView(Button(this, null, 0, R.style.BotaoDiscreto).apply {
            setText(R.string.playlist_nova_mais)
            setOnClickListener {
                Dialogos.nome(this@SalvosActivity, R.string.playlist_nova) { nome ->
                    val id = banco.criarPlaylist(nome)
                    startActivity(Intent(this@SalvosActivity, PlaylistActivity::class.java).putExtra(PlaylistActivity.EXTRA_ID, id))
                }
            }
        })

        val cultos = banco.cultos().filter { it.salvoEm > 0 }
        val hoje = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
        val (proximos, passados) = cultos.partition { it.data >= hoje }
        titulo(R.string.cultos_proximos)
        if (proximos.isEmpty()) texto(getString(R.string.cultos_vazio, Sincronia.DIAS))
        proximos.sortedBy { it.chave }.forEach { culto(it, banco) }
        if (passados.isNotEmpty()) {
            titulo(R.string.cultos_passados)
            passados.forEach { culto(it, banco) }
        }

        texto(getString(R.string.ocupa, Formatter.formatShortFileSize(this, Acervo(banco).tamanho())))
    }

    private fun culto(c: CultoSalvo, banco: Banco) {
        val n = banco.musicasDoCulto(c.chave).size
        val sub = listOfNotNull(c.dirigente.ifBlank { null }?.let { getString(R.string.dirigente, it) },
            resources.getQuantityString(R.plurals.musicas, n, n)).joinToString(" · ")
        linha("${Datas.dia(c.data)} · ${c.titulo}", sub, longo = {
            AlertDialog.Builder(this)
                .setMessage(getString(R.string.culto_apagar, Datas.dia(c.data)))
                .setPositiveButton(R.string.apagar) { _, _ ->
                    banco.apagarCulto(c.chave)
                    montar()
                }
                .setNegativeButton(R.string.cancelar, null)
                .show()
        }) {
            startActivity(Intent(this, PaginaActivity::class.java)
                .putExtra(PaginaActivity.EXTRA_CAMINHO, "/view?order=${c.chave}")
                .putExtra(PaginaActivity.EXTRA_SALVO, true))
        }
    }

    private fun titulo(id: Int) {
        lista.addView(TextView(this).apply {
            setText(id)
            setTextColor(0xFFFFFFFF.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            setPadding(0, dp(24), 0, dp(8))
        })
    }

    private fun texto(t: String) {
        lista.addView(TextView(this).apply {
            text = t
            setTextColor(0x99FFFFFF.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setPadding(0, dp(4), 0, dp(8))
        })
    }

    private fun linha(titulo: String, sub: String, longo: (() -> Unit)? = null, clique: () -> Unit) {
        lista.addView(linhaDeLista(this, titulo, sub).apply {
            setOnClickListener { clique() }
            if (longo != null) setOnLongClickListener { longo(); true }
        })
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}

/** Uma linha tocável (título + detalhe), igual nas telas de salvos e de playlist. */
fun linhaDeLista(ctx: Context, titulo: String, sub: String): LinearLayout {
    val d = ctx.resources.displayMetrics.density
    return LinearLayout(ctx).apply {
        orientation = LinearLayout.VERTICAL
        gravity = Gravity.CENTER_VERTICAL
        minimumHeight = (60 * d).toInt()
        setPadding((16 * d).toInt(), (10 * d).toInt(), (16 * d).toInt(), (10 * d).toInt())
        background = GradientDrawable().apply { cornerRadius = 12 * d; setColor(0x1AFFFFFF) }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            .apply { bottomMargin = (8 * d).toInt() }
        isClickable = true
        isFocusable = true
        foreground = ctx.obtainStyledAttributes(intArrayOf(android.R.attr.selectableItemBackground)).run {
            getDrawable(0).also { recycle() }
        }
        addView(TextView(ctx).apply {
            text = titulo
            setTextColor(0xFFFFFFFF.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
        })
        addView(TextView(ctx).apply {
            text = sub
            setTextColor(0x99FFFFFF.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            visibility = if (sub.isBlank()) View.GONE else View.VISIBLE
        })
    }
}

/** Datas como a pessoa lê: "dom, 22/11". */
object Datas {
    private val entrada = SimpleDateFormat("yyyy-MM-dd", Locale.US)
    private val saida = SimpleDateFormat("EEE, dd/MM", Locale("pt", "BR"))

    fun dia(iso: String): String = try {
        saida.format(entrada.parse(iso.take(10))!!).replace(".", "")
    } catch (e: Exception) {
        iso
    }

    fun quando(ms: Long): String = SimpleDateFormat("dd/MM 'às' HH:mm", Locale("pt", "BR")).format(Date(ms))
}
