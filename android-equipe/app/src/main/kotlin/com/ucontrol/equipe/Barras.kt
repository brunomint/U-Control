package com.ucontrol.equipe

import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/**
 * No Android 15 o app desenha por baixo da barra de status e da de navegação.
 * Isto afasta o conteúdo das duas (e do teclado, para o campo de busca não
 * ficar escondido). Chamar com a view raiz de cada tela.
 */
fun respeitarBarras(raiz: View) {
    val inicio = intArrayOf(raiz.paddingLeft, raiz.paddingTop, raiz.paddingRight, raiz.paddingBottom)
    ViewCompat.setOnApplyWindowInsetsListener(raiz) { v, insets ->
        val b = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
        v.setPadding(inicio[0] + b.left, inicio[1] + b.top, inicio[2] + b.right, inicio[3] + b.bottom)
        WindowInsetsCompat.CONSUMED
    }
}
