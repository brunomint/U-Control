"""Deploy do U-Control pro Raspberry Pi via SSH (paramiko).

Conecta no Pi, atualiza o código (git pull), reinstala dependências,
reaplica o patch do flask_socketio e reinicia o serviço via systemd.
NÃO mexe em migrations de banco automaticamente além do que o próprio
`ucontrol.sh` já faz (`flask db upgrade`) — o passo especial de primeira
vez (`flask db stamp head`, se a coluna media_type já existir) é manual,
documentado no KANBAN.md, e só deve rodar uma única vez, fora deste script.

Uso:
    python scripts/deploy.py --dry-run          # mostra o plano, não conecta
    python scripts/deploy.py                    # pede confirmação, executa
    python scripts/deploy.py --yes               # não pede confirmação

Requer `paramiko` instalado localmente (requirements-dev.txt) — não faz
parte das dependências do Pi.
"""
import argparse
import sys

DEFAULT_HOST = "100.64.46.84"  # Tailscale — funciona de qualquer rede
DEFAULT_USER = "piano-25"
DEFAULT_PATH = "/home/piano-25/ucontrol-v2"  # desde 2026-08-15 (antes 14.3_calendario_U-Control)
DEFAULT_BRANCH = "main"  # desde a v1.0 (2026-10-13); antes "rebuild"
# Há dois serviços com "ucontrol" no nome (o do túnel Cloudflare também);
# a detecção automática pegava o primeiro da lista
DEFAULT_SERVICE = "ucontrol-gunicorn"


# A conexão do Pi com o GitHub às vezes trava sem cair (2026-10-14: um
# fetch ficou 7+ min parado enquanto outro, ao mesmo tempo, respondia em
# 26 s). ServerAlive derruba a conexão muda em ~30 s, timeout corta o
# fetch em 90 s, e tenta até 3 vezes antes de desistir.
FETCH_COMMAND = (
    "for tentativa in 1 2 3; do "
    "GIT_SSH_COMMAND='ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o ConnectTimeout=20' "
    "timeout 90 git fetch origin && exit 0; "
    "echo \"git fetch falhou/travou (tentativa $tentativa de 3), tentando de novo...\" >&2; "
    "done; exit 1"
)


def build_remote_commands(project_path, branch):
    """Monta a sequência de comandos remotos. Cada um só roda se o anterior
    teve sucesso (`&&`), então a primeira falha para o deploy inteiro."""
    return [
        f"cd {project_path}",
        "git status --porcelain",  # checado à parte, não faz parte da cadeia &&
        f"cd {project_path} && {FETCH_COMMAND}",
        f"cd {project_path} && git reset --hard origin/{branch}",
        f"cd {project_path} && venv/bin/pip install -r requirements.txt",
        f"cd {project_path} && venv/bin/python scripts/patch_flask_socketio.py",
    ]


def run(client, command, label):
    print(f"\n$ {command}")
    stdin, stdout, stderr = client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out.strip():
        print(out.strip())
    if err.strip():
        print(err.strip(), file=sys.stderr)
    if exit_code != 0:
        print(f"\nERRO: '{label}' falhou (exit {exit_code}). Deploy interrompido.", file=sys.stderr)
        sys.exit(1)
    return out


def detect_service_name(client):
    """Tenta achar o nome do serviço systemd sem precisar hardcodar —
    procura por unidades cujo nome contenha 'ucontrol'."""
    out = run(
        client,
        "systemctl list-units --type=service --all --no-legend | grep -i ucontrol || true",
        "detectar serviço systemd",
    )
    names = [line.split()[0] for line in out.strip().splitlines() if line.strip()]
    return names[0] if names else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"IP/hostname do Pi (default: {DEFAULT_HOST}, Tailscale)")
    parser.add_argument("--user", default=DEFAULT_USER, help=f"usuário SSH (default: {DEFAULT_USER})")
    parser.add_argument("--path", default=DEFAULT_PATH, help=f"caminho do projeto no Pi (default: {DEFAULT_PATH})")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help=f"branch a fazer deploy (default: {DEFAULT_BRANCH})")
    parser.add_argument("--service", default=DEFAULT_SERVICE, help=f"nome do serviço systemd (default: {DEFAULT_SERVICE})")
    parser.add_argument("--dry-run", action="store_true", help="só mostra o plano, não conecta em lugar nenhum")
    parser.add_argument("--yes", action="store_true", help="não pede confirmação antes de executar")
    args = parser.parse_args()

    print("=== Plano de deploy ===")
    print(f"Host:    {args.user}@{args.host}")
    print(f"Path:    {args.path}")
    print(f"Branch:  {args.branch}")
    print(f"Serviço: {args.service or '(detectar automaticamente)'}")
    print()
    print("Passos: git reset --hard origin/<branch> -> pip install -r requirements.txt")
    print("        -> reaplicar patch flask_socketio -> restart do serviço systemd")
    print()
    print("NÃO inclui: migrations de banco (o ucontrol.sh já roda 'flask db upgrade'")
    print("sozinho ao iniciar) nem o passo especial de primeira migração (stamp head),")
    print("que é manual e único — ver KANBAN.md.")

    if args.dry_run:
        print("\n--dry-run: nada foi executado.")
        return 0

    if not args.yes:
        resposta = input(f"\nConectar em {args.user}@{args.host} e aplicar o deploy? [digite 'sim' pra confirmar] ")
        if resposta.strip().lower() != "sim":
            print("Cancelado.")
            return 1

    try:
        import paramiko
    except ImportError:
        print(
            "\nERRO: paramiko não está instalado. Rode: pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.load_system_host_keys()
    print(f"\nConectando em {args.user}@{args.host}...")
    client.connect(args.host, username=args.user)

    try:
        status = run(client, f"cd {args.path} && git status --porcelain", "checar estado do git no Pi")
        if status.strip():
            print(
                "\nAVISO: há mudanças não commitadas no Pi. 'git reset --hard' vai descartá-las.",
                file=sys.stderr,
            )
            if not args.yes:
                resposta = input("Continuar mesmo assim? [digite 'sim' pra confirmar] ")
                if resposta.strip().lower() != "sim":
                    print("Cancelado.")
                    return 1

        run(client, f"cd {args.path} && {FETCH_COMMAND}", "git fetch")
        run(client, f"cd {args.path} && git reset --hard origin/{args.branch}", "git reset --hard")
        run(client, f"cd {args.path} && venv/bin/pip install -r requirements.txt", "pip install")
        run(client, f"cd {args.path} && venv/bin/python scripts/patch_flask_socketio.py", "patch flask_socketio")

        service = args.service or detect_service_name(client)
        if not service:
            print(
                "\nAVISO: não achei nenhum serviço systemd com 'ucontrol' no nome. "
                "Reinicie manualmente (ou passe --service <nome>).",
                file=sys.stderr,
            )
            return 1

        run(client, f"sudo systemctl restart {service}", f"restart {service}")
        run(client, f"sudo systemctl is-active {service}", f"verificar {service}")
        print(f"\nDeploy concluído. Serviço '{service}' reiniciado.")
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
