"""Screenshot reutilizável via Chrome DevTools Protocol — usado pra
verificação visual da unificação de renderização VexFlow (ver plano em
.claude/plans/harmonic-mixing-breeze.md), mas genérico o bastante pra
qualquer página do app.

Requer um Chrome já rodando com --remote-debugging-port (a mesma
instância usada em outras verificações deste projeto). Pra páginas com
@login_required, passe uma session cookie válida (extraída do navegador
já logado — este script não faz login sozinho).

Uso:
    python scripts/cdp_screenshot.py <url> <output.png> [--cookie VALOR]
        [--cdp-port 9333] [--wait-vexflow] [--width W --height H]

Como módulo:
    from scripts.cdp_screenshot import screenshot
    screenshot("http://127.0.0.1:8585/sheet_editor/321", "out.png",
               cookie=cookie_val, wait_vexflow=True)
"""
import argparse
import base64
import json
import sys
import time

import requests
import websocket


def screenshot(url, output_path, cookie=None, cdp_port=9333, wait_vexflow=False,
                width=None, height=None, extra_wait=1.5):
    """Navega até `url` num Chrome headless via CDP e salva um PNG.

    Se `wait_vexflow` for True, aguarda até existir pelo menos uma nota
    renderizada (`svg .vf-stavenote`) antes de tirar o screenshot, ou
    desiste após ~8s (útil pra páginas de partitura, onde o VexFlow
    carrega via import assíncrono)."""
    r = requests.put(f"http://127.0.0.1:{cdp_port}/json/new?about:blank")
    target = r.json()
    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
    counter = {"i": 0}

    def send(method, params=None):
        counter["i"] += 1
        id_ = counter["i"]
        ws.send(json.dumps({"id": id_, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == id_:
                return msg

    try:
        send("Network.enable")
        if cookie:
            domain = url.split("/")[2].split(":")[0]
            send("Network.setCookie", {"name": "session", "value": cookie, "domain": domain, "path": "/"})
        send("Page.enable")
        send("Runtime.enable")
        if width and height:
            send("Emulation.setDeviceMetricsOverride",
                 {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
        send("Page.navigate", {"url": url})
        time.sleep(extra_wait)

        if wait_vexflow:
            deadline = time.time() + 8
            while time.time() < deadline:
                res = send("Runtime.evaluate", {
                    "expression": "document.querySelectorAll('svg .vf-stavenote').length",
                    "returnByValue": True,
                })
                count = res.get("result", {}).get("result", {}).get("value", 0)
                if count and count > 0:
                    break
                time.sleep(0.5)

        shot = send("Page.captureScreenshot", {"format": "png"})
        data = base64.b64decode(shot["result"]["data"])
        with open(output_path, "wb") as f:
            f.write(data)
        return output_path
    finally:
        send("Page.close")
        ws.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("output")
    parser.add_argument("--cookie", default=None, help="Valor da session cookie (páginas @login_required)")
    parser.add_argument("--cdp-port", type=int, default=9333)
    parser.add_argument("--wait-vexflow", action="store_true")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    args = parser.parse_args()

    out = screenshot(args.url, args.output, cookie=args.cookie, cdp_port=args.cdp_port,
                      wait_vexflow=args.wait_vexflow, width=args.width, height=args.height)
    print(f"salvo: {out}")


if __name__ == '__main__':
    sys.exit(main())
