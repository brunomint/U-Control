package com.ucontrol.equipe

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import kotlin.concurrent.thread

/**
 * Primeira tela: acha a igreja e segue para o menu.
 * 1. o endereço salvo, se ainda responde;
 * 2. a varredura do Wi-Fi (Descoberta);
 * 3. se nada der certo, a pessoa digita o endereço (IP local ou da internet).
 */
class InicioActivity : AppCompatActivity() {

    private lateinit var status: TextView
    private lateinit var progresso: ProgressBar
    private lateinit var acoes: View
    private lateinit var abrirSalvo: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_inicio)
        respeitarBarras(findViewById(android.R.id.content))
        status = findViewById(R.id.status)
        progresso = findViewById(R.id.progresso)
        acoes = findViewById(R.id.acoes)
        abrirSalvo = findViewById(R.id.btnAbrirSalvo)

        findViewById<Button>(R.id.btnProcurar).setOnClickListener { procurar(usarSalvo = false) }
        findViewById<Button>(R.id.btnDigitar).setOnClickListener { pedirEndereco() }
        findViewById<Button>(R.id.btnSalvos).apply {
            visibility = if (Servidor.salvo(this@InicioActivity) != null) View.VISIBLE else View.GONE
            setOnClickListener { startActivity(Intent(this@InicioActivity, SalvosActivity::class.java)) }
        }

        procurar(usarSalvo = !intent.getBooleanExtra(EXTRA_TROCAR, false))
    }

    private fun procurar(usarSalvo: Boolean) {
        mostrarProcurando(getString(R.string.procurando))
        thread {
            val salvo = Servidor.salvo(this)
            if (usarSalvo && salvo != null) {
                val ok = Servidor.identificar(salvo.endereco)
                if (ok != null) return@thread runOnUiThread { entrar(ok) }
            }
            val achadas = Descoberta.procurar(this)
            runOnUiThread {
                when (achadas.size) {
                    0 -> naoAchou(salvo)
                    1 -> entrar(achadas[0])
                    else -> escolher(achadas)
                }
            }
        }
    }

    private fun escolher(achadas: List<Igreja>) {
        AlertDialog.Builder(this)
            .setTitle(R.string.qual_igreja)
            .setItems(achadas.map { "${it.titulo}\n${it.endereco}" }.toTypedArray()) { _, i -> entrar(achadas[i]) }
            .setOnCancelListener { naoAchou(Servidor.salvo(this)) }
            .show()
    }

    private fun naoAchou(salvo: Igreja?) {
        progresso.visibility = View.GONE
        acoes.visibility = View.VISIBLE
        status.setText(R.string.nao_achou)
        if (salvo != null) {
            abrirSalvo.visibility = View.VISIBLE
            abrirSalvo.text = getString(R.string.abrir_mesmo_assim, salvo.titulo)
            abrirSalvo.setOnClickListener { entrar(salvo, salvar = false) }
        } else {
            abrirSalvo.visibility = View.GONE
        }
    }

    private fun pedirEndereco() {
        val campo = EditText(this).apply {
            hint = getString(R.string.dica_endereco)
            setSingleLine(true)
            setSelectAllOnFocus(true)   // digitar já troca o endereço antigo
            Servidor.salvo(this@InicioActivity)?.let { setText(it.endereco.substringAfter("://")) }
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.endereco_titulo)
            .setMessage(R.string.endereco_explica)
            .setView(campo)
            .setPositiveButton(R.string.conectar) { _, _ ->
                val endereco = Servidor.normalizar(campo.text.toString())
                if (endereco == null) {
                    Toast.makeText(this, R.string.endereco_invalido, Toast.LENGTH_LONG).show()
                } else {
                    testarEndereco(endereco)
                }
            }
            .setNegativeButton(R.string.cancelar, null)
            .show()
    }

    private fun testarEndereco(endereco: String) {
        mostrarProcurando(getString(R.string.testando, endereco))
        thread {
            val ok = Servidor.identificar(endereco, esperaMs = 6000)
            runOnUiThread {
                if (ok != null) {
                    entrar(ok)
                } else {
                    naoAchou(Servidor.salvo(this))
                    status.text = getString(R.string.endereco_nao_respondeu, endereco)
                }
            }
        }
    }

    private fun mostrarProcurando(texto: String) {
        status.text = texto
        progresso.visibility = View.VISIBLE
        acoes.visibility = View.GONE
    }

    private fun entrar(igreja: Igreja, salvar: Boolean = true) {
        if (salvar) Servidor.salvar(this, igreja)
        startActivity(Intent(this, MenuActivity::class.java))
        finish()
    }

    companion object {
        /** Veio do "Trocar de igreja": não usa o endereço salvo. */
        const val EXTRA_TROCAR = "trocar"
    }
}
