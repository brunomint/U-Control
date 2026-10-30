#!/usr/bin/env bash
# Backup do U-Control do Pi pro PC (roda no PC, puxando do Pi por SSH).
#
# O que guarda, em ~/Backups/U-Control/:
#   banco/users-AAAA-MM-DD_HHMM.db  cópia consistente do banco (API de backup
#                                    do SQLite — dá pra copiar com o site no ar)
#   instance/secret_key              chave das sessões do site
#   midia/imagens, midia/audio       fotos e áudios (espelho; o que foi apagado
#                                    no Pi continua aqui)
#   backup.log                       histórico de cada execução
# Mantém as últimas $MANTER cópias do banco.
#
# Agendado pelo timer do systemd do usuário (scripts/ucontrol-backup.timer):
# todo dia e, se o PC estava desligado no horário, assim que ligar.
# Rodar na mão: scripts/backup_do_pi.sh
set -euo pipefail

# Endereço, usuário e pasta do Pi: scripts/pi.conf (fora do Git — modelo em
# pi.conf.example), o mesmo do deploy.py. UCONTROL_PI / UCONTROL_APP ainda valem.
CONF="$(dirname "$(readlink -f "$0")")/pi.conf"
[ -f "$CONF" ] && . "$CONF"
PI="${UCONTROL_PI:-${PI_USER:-}@${PI_HOST:-}}"
APP="${UCONTROL_APP:-${PI_PATH:-}}"
if [ "$PI" = "@" ] || [ -z "$APP" ]; then
    echo "Falta o destino do Pi: copie scripts/pi.conf.example para scripts/pi.conf e preencha." >&2
    exit 1
fi
DEST="${UCONTROL_BACKUP_DIR:-$HOME/Backups/U-Control}"
MANTER="${UCONTROL_BACKUP_MANTER:-30}"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20)

mkdir -p "$DEST/banco" "$DEST/instance" "$DEST/midia"
chmod 700 "$DEST"
LOG="$DEST/backup.log"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
falhou() {
    log "ERRO: $*"
    command -v notify-send >/dev/null && notify-send -u critical "Backup do U-Control falhou" "$*" || true
    exit 1
}

log "início"
"${SSH[@]}" "$PI" true 2>/dev/null || falhou "Pi não respondeu por SSH ($PI)"

# 1) Banco: cópia consistente feita no próprio Pi (o banco está em uso,
#    copiar o arquivo direto pode pegar uma escrita pela metade)
carimbo="$(date +%F_%H%M)"
tmp_pi="/tmp/ucontrol-backup-$carimbo.db"
"${SSH[@]}" "$PI" "cd '$APP' && venv/bin/python -c \"
import sqlite3, sys
src = sqlite3.connect('instance/users.db')
dst = sqlite3.connect('$tmp_pi')
src.backup(dst)
ok = dst.execute('PRAGMA integrity_check').fetchone()[0]
dst.close(); src.close()
sys.exit(0 if ok == 'ok' else 1)
\"" || falhou "não consegui copiar o banco no Pi (ou a cópia veio corrompida)"
destino_db="$DEST/banco/users-$carimbo.db"
rsync -a -e "${SSH[*]}" "$PI:$tmp_pi" "$destino_db" || falhou "não consegui trazer o banco do Pi"
"${SSH[@]}" "$PI" "rm -f '$tmp_pi'" || true
chmod 600 "$destino_db"
log "banco: $(basename "$destino_db") ($(du -h "$destino_db" | cut -f1))"

# 2) Chave das sessões
rsync -a -e "${SSH[*]}" "$PI:$APP/instance/secret_key" "$DEST/instance/" || falhou "não consegui trazer instance/secret_key"
chmod 600 "$DEST/instance/secret_key"

# 3) Fotos e áudios (só o que mudou; sem --delete de propósito)
for pasta in imagens audio; do
    rsync -a -e "${SSH[*]}" "$PI:$APP/static/$pasta/" "$DEST/midia/$pasta/" || falhou "não consegui trazer static/$pasta"
done
log "mídia: $(du -sh "$DEST/midia" | cut -f1)"

# 4) Só as últimas $MANTER cópias do banco
ls -1t "$DEST"/banco/users-*.db 2>/dev/null | tail -n +"$((MANTER + 1))" | xargs -r rm -f
log "ok — $(ls -1 "$DEST"/banco/users-*.db | wc -l) cópia(s) do banco guardadas"
