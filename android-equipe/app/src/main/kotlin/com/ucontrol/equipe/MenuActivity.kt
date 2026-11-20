package com.ucontrol.equipe

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/** O que a equipe abre: as páginas do U-Control que já existem. */
class MenuActivity : AppCompatActivity() {

    companion object {
        private var aquecido = false
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_menu)
        respeitarBarras(findViewById(android.R.id.content))
        aquecerNavegador()
    }

    /**
     * A primeira página aberta carrega o motor do Chrome (WebView), o que trava
     * a tela por um instante — num celular simples, segundos. Carregar quando o
     * menu acabou de aparecer faz o toque em "Cifras" abrir sem essa espera.
     */
    private fun aquecerNavegador() {
        if (aquecido) return
        android.os.Looper.myQueue().addIdleHandler {
            try {
                android.webkit.WebView(applicationContext).destroy()
                aquecido = true
            } catch (e: Exception) {
                // sem WebView no aparelho: a PaginaActivity mostra o erro
            }
            false
        }
    }

    override fun onResume() {
        super.onResume()
        val igreja = Servidor.salvo(this) ?: return trocar()
        findViewById<TextView>(R.id.igreja).text = igreja.nome.ifBlank { getString(R.string.app_name) }
        findViewById<TextView>(R.id.endereco).text = igreja.endereco.substringAfter("://")

        ligar(R.id.btnCifras, "/view")
        ligar(R.id.btnProximo, "/agenda/hoje")
        ligar(R.id.btnAgenda, "/agenda")
        ligar(R.id.btnOperador, "/login?next=%2F")
        findViewById<Button>(R.id.btnTrocar).setOnClickListener { trocar() }
        findViewById<Button>(R.id.btnSalvos).setOnClickListener {
            startActivity(Intent(this, SalvosActivity::class.java))
        }
        Sincronia.ouvir(ouvinte)
        Sincronia.sincronizar(this)
    }

    private val ouvinte: (String) -> Unit = { findViewById<TextView>(R.id.estadoSalvos).text = it }

    override fun onPause() {
        super.onPause()
        Sincronia.parar(ouvinte)
    }

    private fun ligar(id: Int, caminho: String) {
        findViewById<Button>(id).setOnClickListener {
            startActivity(Intent(this, PaginaActivity::class.java).putExtra(PaginaActivity.EXTRA_CAMINHO, caminho))
        }
    }

    private fun trocar() {
        startActivity(Intent(this, InicioActivity::class.java).putExtra(InicioActivity.EXTRA_TROCAR, true))
        finish()
    }
}
