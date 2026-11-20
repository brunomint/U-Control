package com.ucontrol.equipe

import android.content.Context
import android.net.ConnectivityManager
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Procura o U-Control na rede do Wi-Fi: testa a porta 8585 em cada endereço
 * da rede e confirma por /api/identidade. O anúncio mDNS (main.py
 * registrar_mdns) não é ligado no servidor, por isso a varredura.
 *
 * Numa rede de casa ou de igreja (/24 = 254 endereços) leva poucos segundos.
 * Redes maiores que /22 não são varridas: seriam milhares de endereços.
 */
object Descoberta {
    private const val ESPERA_PORTA_MS = 350
    private const val MAX_ENDERECOS = 1024

    /** Bloqueia até terminar: chamar fora da tela principal. */
    fun procurar(ctx: Context): List<Igreja> {
        val candidatos = enderecosDaRede(ctx)
        if (candidatos.isEmpty()) return emptyList()
        val achadas = java.util.Collections.synchronizedList(mutableListOf<Igreja>())
        val pool = Executors.newFixedThreadPool(48)
        for (ip in candidatos) {
            pool.execute {
                if (portaAberta(ip)) {
                    Servidor.identificar("http://$ip:${Servidor.PORTA}")?.let { achadas.add(it) }
                }
            }
        }
        pool.shutdown()
        pool.awaitTermination(30, TimeUnit.SECONDS)
        // O mesmo servidor no cabo e no Wi-Fi responde duas vezes: fica o 1º endereço
        return achadas.sortedBy { it.endereco }.distinctBy { it.id.ifBlank { it.endereco } }
    }

    private fun portaAberta(ip: String): Boolean = try {
        Socket().use { it.connect(InetSocketAddress(ip, Servidor.PORTA), ESPERA_PORTA_MS); true }
    } catch (e: Exception) {
        false
    }

    /** Os endereços da rede atual (sem o do próprio celular). */
    private fun enderecosDaRede(ctx: Context): List<String> {
        val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val props = cm.getLinkProperties(cm.activeNetwork) ?: return emptyList()
        val link = props.linkAddresses.firstOrNull { it.address is Inet4Address } ?: return emptyList()
        val prefixo = link.prefixLength
        if (prefixo < 22 || prefixo > 30) return emptyList()

        val meu = link.address.address.fold(0L) { acc, b -> (acc shl 8) or (b.toLong() and 0xff) }
        val mascara = (0xffffffffL shl (32 - prefixo)) and 0xffffffffL
        val rede = meu and mascara
        val total = (1L shl (32 - prefixo)).coerceAtMost(MAX_ENDERECOS.toLong())

        return (1 until total - 1)
            .map { rede + it }
            .filter { it != meu }
            .map { n ->
                InetAddress.getByAddress(byteArrayOf(
                    (n shr 24).toByte(), (n shr 16).toByte(), (n shr 8).toByte(), n.toByte()
                )).hostAddress ?: ""
            }
            .filter { it.isNotEmpty() }
    }
}
