"""Preparado e "acompanhar ao vivo" por aparelho, e quem cuida do palco —
os cenários de dois operadores do culto de 01/11/2026."""
import pytest

import connections
import display_state
import preparado
import telao
from test_smoke import _operator_socket

FOTO = {"kind": "image", "payload": {"image_url": "/static/imagens/a.jpg"}, "label": "a.jpg"}
LETRA = {"kind": "lyrics", "payload": {"songId": 1, "sectionIndex": 0, "title": "V1"}, "label": "V1"}


@pytest.fixture
def dois(app):
    ipad, vitor = _operator_socket(app), _operator_socket(app, "vitor")
    ds = list(connections.socketio_clients_by_sid.values())
    yield ipad, vitor, ds[-2]["device"], ds[-1]["device"]
    for s in (ipad, vitor):
        s.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": False})
        s.disconnect()
    telao.set_monitor(None)


def _status(sock):
    return [m["args"][0] for m in sock.get_received() if m["name"] == "telao_status"][-1]


def _nomes(sock):
    return [m["name"] for m in sock.get_received()]


def _do(app, kind, device):
    with app.app_context():
        return preparado.pegar(kind, device) is not None


def test_cada_aparelho_tem_seu_preparado(app, dois):
    ipad, vitor, d_ipad, d_vitor = dois
    ipad.emit("set_display_mode", {"mode": "public"})
    vitor.emit("set_display_mode", {"mode": "monitor"})
    ipad.emit("stage_content", {**FOTO, "label": "do iPad"})
    vitor.emit("stage_content", {**FOTO, "label": "do Vitor"})
    assert _do(app, "image", d_ipad) and _do(app, "image", d_vitor)
    ipad.get_received(); vitor.get_received()
    ipad.emit("stage_content", {**FOTO, "label": "do iPad 2"})
    assert [i["label"] for i in _status(ipad)["staged"]] == ["do iPad 2"]
    assert [i["label"] for i in _status(vitor)["staged"]] == ["do Vitor"]


def test_liberar_nao_solta_o_preparado_do_outro(app, dois):
    ipad, vitor, d_ipad, d_vitor = dois
    vitor.emit("stage_content", LETRA)
    ipad.get_received()
    ipad.emit("release_staged_content", {"kind": "lyrics"})
    assert _do(app, "lyrics", d_vitor)
    assert "content_released" not in _nomes(ipad)


def test_descartar_e_avisos_ficam_no_aparelho(app, dois):
    ipad, vitor, d_ipad, d_vitor = dois
    ipad.get_received(); vitor.get_received()
    vitor.emit("stage_content", FOTO)
    assert "content_staged" in _nomes(vitor) and "content_staged" not in _nomes(ipad)
    ipad.emit("discard_staged_content", {"kind": "image"})
    assert _do(app, "image", d_vitor)


def test_parar_e_trocar_de_modo_nao_atingem_o_outro(dois):
    ipad, vitor, d_ipad, d_vitor = dois
    vitor.emit("stage_content", LETRA)
    vitor.emit("release_staged_content", {"kind": "lyrics"})
    assert display_state.follow_kind(d_vitor) == "lyrics"
    ipad.emit("set_display_mode", {"exclude_monitor": True, "monitor_only": False})
    ipad.emit("stop_live_follow", {})
    assert display_state.follow_kind(d_vitor) == "lyrics"
    assert not display_state._follow(d_vitor)["parado"]


def test_status_traz_o_acompanhar_de_cada_um(dois):
    ipad, vitor, d_ipad, d_vitor = dois
    vitor.emit("stage_content", LETRA)
    vitor.emit("release_staged_content", {"kind": "lyrics"})
    ipad.get_received(); vitor.get_received()
    telao.broadcast_status()
    assert _status(vitor)["follow"] == "lyrics" and _status(ipad)["follow"] is None


def test_mudar_o_publico_encerra_o_acompanhar_do_outro(dois):
    """Sem isto, a próxima seção do iPad atropelaria a foto do Vitor."""
    ipad, vitor, d_ipad, d_vitor = dois
    ipad.emit("stage_content", LETRA)
    ipad.emit("release_staged_content", {"kind": "lyrics"})
    vitor.emit("assumir_tela", {"tela": "public"})   # Vitor assume o público
    vitor.emit("show_image", {"image_url": "/static/imagens/a.jpg"})
    assert display_state.follow_kind(d_ipad) is None


def test_acao_so_no_palco_nao_encerra_o_acompanhar_do_publico(dois):
    ipad, vitor, d_ipad, d_vitor = dois
    ipad.emit("set_display_mode", {"exclude_monitor": True, "monitor_only": False})
    vitor.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": True})
    ipad.emit("stage_content", LETRA)
    ipad.emit("release_staged_content", {"kind": "lyrics"})
    vitor.emit("show_monitor_content", {"url": "/clock"})
    assert display_state.follow_kind(d_ipad) == "lyrics"


def test_so_monitor_nao_perde_o_acompanhar_quando_o_publico_muda(dois):
    ipad, vitor, d_ipad, d_vitor = dois
    vitor.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": True})
    display_state._follow(d_vitor)["kind"] = "lyrics"
    ipad.emit("show_image", {"image_url": "/static/imagens/a.jpg"})
    assert display_state.follow_kind(d_vitor) == "lyrics"


def test_palco_com_mostra_o_nome_e_some_quando_ele_sai(dois):
    ipad, vitor, d_ipad, d_vitor = dois
    vitor.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": True})
    ipad.get_received(); vitor.get_received()
    telao.broadcast_status()
    assert _status(ipad)["palco_com"] == "vitor"
    assert _status(vitor)["palco_com"] is None
    for sid, info in list(connections.socketio_clients_by_sid.items()):
        if info["device"] == d_vitor:
            del connections.socketio_clients_by_sid[sid]
    telao.broadcast_status()
    assert _status(ipad)["palco_com"] is None


def test_assumir_o_palco(dois):
    ipad, vitor, d_ipad, d_vitor = dois
    vitor.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": True})
    vitor.emit("stage_content", LETRA)
    vitor.emit("release_staged_content", {"kind": "lyrics"})
    vitor.get_received()
    ipad.emit("set_display_mode", {"mode": "public"})
    ipad.emit("assumir_palco", {})
    assert display_state.device_mode(d_ipad) == "all"   # público + palco assumido
    # Vitor só tinha o palco: fica sem tela (antes caía em "Só público")
    assert display_state.device_mode(d_vitor) == "none"
    assert display_state.follow_kind(d_vitor) is None
    recebidos = vitor.get_received()
    assert any(m["name"] == "tela_assumida" and m["args"][0]["por"] == "tester" for m in recebidos)


def test_assumir_exige_login(app, dois):
    ipad, vitor, d_ipad, d_vitor = dois
    from extensions import socketio
    intruso = socketio.test_client(app)
    vitor.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": True})
    intruso.emit("assumir_palco", {})
    assert display_state.device_mode(d_vitor) == "monitor"
    intruso.disconnect()


def test_stream_deck_libera_o_preparado_mais_recente_e_avisa_o_dono(app, client, dois):
    ipad, vitor, d_ipad, d_vitor = dois
    from blueprints import atalhos
    telao.set_public('clock', '/clock')      # sem foto na tela: a foto fica preparada
    vitor.emit("stage_content", FOTO)
    vitor.get_received()
    with app.app_context():
        chave = atalhos.chave()
    assert client.get(f"/api/atalho/liberar?chave={chave}").get_json()["ok"]
    assert not _do(app, "image", d_vitor)
    assert "content_released" in _nomes(vitor)
