package com.ucontrol.equipe

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ServidorTest {

    @Test
    fun ipDaRedeLocalGanhaHttpEAPorta() {
        assertEquals("http://192.168.0.50:8585", Servidor.normalizar("192.168.0.50"))
        assertEquals("http://192.168.0.50:8585", Servidor.normalizar("  192.168.0.50/ "))
    }

    @Test
    fun portaDigitadaEhMantida() {
        assertEquals("http://192.168.0.50:9000", Servidor.normalizar("192.168.0.50:9000"))
        assertEquals("http://ucontrol.local:8585", Servidor.normalizar("ucontrol.local"))
    }

    @Test
    fun siteDaInternetUsaHttps() {
        assertEquals("https://minhaigreja.com", Servidor.normalizar("minhaigreja.com"))
        assertEquals("https://minhaigreja.com", Servidor.normalizar("minhaigreja.com/"))
    }

    @Test
    fun enderecoCompletoFicaComoVeio() {
        assertEquals("http://10.0.0.5:8585", Servidor.normalizar("http://10.0.0.5:8585/"))
        assertEquals("https://x.com", Servidor.normalizar("https://x.com"))
    }

    @Test
    fun vazioOuComEspacoNaoServe() {
        assertNull(Servidor.normalizar(""))
        assertNull(Servidor.normalizar("minha igreja"))
    }

    @Test
    fun nomeDoArquivoMandadoPeloServidor() {
        assertEquals("Hino.pdf", Arquivos.nomeDoArquivo("inline; filename=\"Hino.pdf\""))
        assertEquals("Ação.pdf", Arquivos.nomeDoArquivo("attachment; filename*=UTF-8''A%C3%A7%C3%A3o.pdf"))
        assertNull(Arquivos.nomeDoArquivo(null))
        assertNull(Arquivos.nomeDoArquivo("inline"))
    }
}
