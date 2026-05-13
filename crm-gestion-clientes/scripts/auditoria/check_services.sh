#!/usr/bin/env bash
# =============================================================================
# check_services.sh — Auditoría de servicios activos del sistema
#
# Comprueba:
#   1. Servicios en ejecución sospechosos o innecesarios
#   2. Servicios con fallos recientes
#   3. Servicios que se inician al arranque (innecesarios)
#   4. Procesos con privilegios elevados
#   5. Cron jobs del sistema y de usuarios
#
# Uso: bash check_services.sh
# =============================================================================

source "$(dirname "$0")/lib_comun.sh"

log_inicio_modulo "SERVICIOS"
titulo "AUDITORÍA DE SERVICIOS ACTIVOS"

# ── Lista de servicios considerados de riesgo si están activos ────────────────
declare -A SERVICIOS_RIESGO=(
    ["telnet"]="Telnet: comunicación sin cifrar — usar SSH"
    ["rsh"]="Remote Shell: obsoleto y sin cifrar"
    ["rlogin"]="Remote Login: sin cifrar"
    ["rexec"]="Remote Exec: sin autenticación"
    ["tftp"]="TFTP: transferencia sin autenticación"
    ["vsftpd"]="FTP: sin cifrar — usar SFTP/FTPS"
    ["proftpd"]="FTP: sin cifrar — usar SFTP/FTPS"
    ["wu-ftpd"]="FTP: obsoleto y vulnerable"
    ["xinetd"]="inetd: superservidor obsoleto — revisar servicios que lanza"
    ["inetd"]="inetd: superservidor obsoleto"
    ["nfs-server"]="NFS: permisos de montaje pueden ser excesivos"
    ["rpcbind"]="RPC portmapper: requerido por NFS/NIS"
    ["nis"]="NIS: autenticación de red obsoleta e insegura"
    ["talk"]="Talk: comunicación sin cifrar"
    ["avahi-daemon"]="Avahi/mDNS: descubrimiento de red — filtra información"
    ["cups"]="CUPS: servidor de impresión — innecesario en servidores"
)

# ── Servicios que deberían estar activos (referencia) ─────────────────────────
SERVICIOS_ESPERADOS=("sshd" "cron" "rsyslog" "systemd-journald")

# ══════════════════════════════════════════════════════════════════════════════
# 1. SERVICIOS EN EJECUCIÓN
# ══════════════════════════════════════════════════════════════════════════════
seccion "Servicios activos (systemd)"
echo ""

if command -v systemctl &>/dev/null; then
    TOTAL_SERVICIOS=$(systemctl list-units --type=service --state=running 2>/dev/null \
        | grep -c "\.service" || echo 0)
    info "Total servicios en ejecución: ${TOTAL_SERVICIOS}"
    echo ""

    # Servicios de riesgo activos
    for servicio in "${!SERVICIOS_RIESGO[@]}"; do
        if systemctl is-active --quiet "${servicio}" 2>/dev/null; then
            warn "Servicio activo: ${servicio} — ${SERVICIOS_RIESGO[${servicio}]}"
        fi
    done

    # Servicios esperados
    for servicio in "${SERVICIOS_ESPERADOS[@]}"; do
        if systemctl is-active --quiet "${servicio}" 2>/dev/null; then
            ok "Servicio esperado activo: ${servicio}"
        else
            warn "Servicio esperado NO activo: ${servicio}"
        fi
    done

    # Servicios fallidos
    echo ""
    info "Servicios con fallos:"
    FALLOS=$(systemctl list-units --type=service --state=failed 2>/dev/null \
        | grep "\.service" | awk '{print $1}')

    if [[ -z "${FALLOS}" ]]; then
        ok "Sin servicios en estado fallido"
    else
        while IFS= read -r servicio_fallido; do
            [[ -z "${servicio_fallido}" ]] && continue
            crit "Servicio fallido: ${servicio_fallido}"
            # Últimas líneas del log del servicio
            journalctl -u "${servicio_fallido}" -n 3 --no-pager 2>/dev/null \
                | tail -3 | while IFS= read -r log_linea; do
                    echo -e "    ${GRIS}${log_linea}${NC}"
                done
        done <<< "${FALLOS}"
    fi

else
    # Sin systemd — usar service o ps
    if command -v service &>/dev/null; then
        info "systemd no disponible — usando 'service --status-all'"
        for servicio in "${!SERVICIOS_RIESGO[@]}"; do
            if service "${servicio}" status &>/dev/null 2>&1; then
                warn "Servicio activo: ${servicio} — ${SERVICIOS_RIESGO[${servicio}]}"
            fi
        done
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 2. SERVICIOS HABILITADOS EN EL ARRANQUE
# ══════════════════════════════════════════════════════════════════════════════
seccion "Servicios habilitados al arranque (potencialmente innecesarios)"
echo ""

if command -v systemctl &>/dev/null; then
    TOTAL_ENABLED=$(systemctl list-unit-files --type=service --state=enabled 2>/dev/null \
        | grep -c "enabled" || echo 0)
    info "Total servicios habilitados al arranque: ${TOTAL_ENABLED}"

    # Detectar servicios de riesgo habilitados
    ENCONTRADO_RIESGO_BOOT=false
    for servicio in "${!SERVICIOS_RIESGO[@]}"; do
        ESTADO=$(systemctl is-enabled "${servicio}" 2>/dev/null)
        if [[ "${ESTADO}" == "enabled" ]]; then
            warn "Habilitado al arranque: ${servicio} — ${SERVICIOS_RIESGO[${servicio}]}"
            ENCONTRADO_RIESGO_BOOT=true
        fi
    done

    [[ "${ENCONTRADO_RIESGO_BOOT}" == false ]] && \
        ok "Sin servicios de riesgo conocidos habilitados al arranque"

    # Listar servicios habilitados (para revisión manual)
    echo ""
    info "Listado de servicios habilitados (revisar manualmente):"
    systemctl list-unit-files --type=service --state=enabled 2>/dev/null \
        | grep "enabled" | awk '{print $1}' \
        | grep -vE 'systemd|getty|network|dbus|ssh|cron|rsyslog|ufw|apparmor' \
        | head -20 | while IFS= read -r srv; do
            echo -e "    ${GRIS}${srv}${NC}"
        done
fi

# ══════════════════════════════════════════════════════════════════════════════
# 3. PROCESOS CON PRIVILEGIOS (root)
# ══════════════════════════════════════════════════════════════════════════════
seccion "Procesos corriendo como root"
echo ""

# Procesos root que no son del sistema
PS_ROOT=$(ps aux 2>/dev/null | awk '$1=="root" && $11!~/^\[/ {print $11}' \
    | sort -u | grep -vE '^(/usr/lib|/lib|/usr/sbin|/sbin|/usr/bin/(python|perl|ssh|bash|sh))')

PROC_SOSPECHOSOS=(
    "nc" "netcat" "ncat"        # netcat — puede crear backdoors
    "socat"                     # proxy de red — puede ser backdoor
    "python" "python3" "ruby" "perl" "php"  # intérpretes como root son sospechosos
    "wget" "curl"               # descarga como root en proceso persistente
    "nmap" "masscan"            # escaneo de red corriendo como root
    "tcpdump" "wireshark"       # captura de paquetes
    "base64"                    # codificación — puede ser exfiltración
    "xxd"                       # conversión hex — puede ser exfiltración
)

ENCONTRADO_SOSPECHOSO=false
for proc in "${PROC_SOSPECHOSOS[@]}"; do
    if ps aux 2>/dev/null | grep -v grep | awk '$1=="root"' | grep -q "${proc}"; then
        crit "Proceso sospechoso corriendo como root: ${proc}"
        ps aux | grep -v grep | awk '$1=="root"' | grep "${proc}" \
            | awk '{print "    PID:",$2, "CMD:",$11,$12,$13}' | head -3
        ENCONTRADO_SOSPECHOSO=true
    fi
done

[[ "${ENCONTRADO_SOSPECHOSO}" == false ]] && \
    ok "Sin procesos sospechosos detectados corriendo como root"

# Número total de procesos root
TOTAL_PROC_ROOT=$(ps aux 2>/dev/null | awk '$1=="root"' | grep -v "^root.*\[" | wc -l)
info "Total procesos root: ${TOTAL_PROC_ROOT}"

if [[ "${TOTAL_PROC_ROOT}" -gt 50 ]]; then
    warn "Número elevado de procesos root (${TOTAL_PROC_ROOT}) — revisar"
fi

# ══════════════════════════════════════════════════════════════════════════════
# 4. CRON JOBS DEL SISTEMA Y USUARIOS
# ══════════════════════════════════════════════════════════════════════════════
seccion "Cron jobs (sistema y usuarios)"
echo ""

# Crontabs del sistema
CRON_DIRS=("/etc/cron.d" "/etc/cron.daily" "/etc/cron.weekly" "/etc/cron.monthly" "/etc/cron.hourly")

for dir in "${CRON_DIRS[@]}"; do
    if [[ -d "${dir}" ]]; then
        ARCHIVOS=$(ls "${dir}" 2>/dev/null | grep -v "^\." | wc -l)
        if [[ "${ARCHIVOS}" -gt 0 ]]; then
            info "Cron jobs en ${dir}: ${ARCHIVOS} archivo(s)"
            ls "${dir}" 2>/dev/null | grep -v "^\." | while IFS= read -r archivo; do
                echo -e "    ${GRIS}${archivo}${NC}"
            done
        fi
    fi
done

# /etc/crontab
if [[ -f /etc/crontab ]]; then
    info "Contenido de /etc/crontab:"
    grep -v "^#" /etc/crontab | grep -v "^$" | while IFS= read -r linea; do
        echo -e "    ${GRIS}${linea}${NC}"
    done
fi

# Crontabs de usuarios
echo ""
info "Crontabs de usuarios del sistema:"
ENCONTRADO_CRON_USER=false

# Iterar usuarios con shell válida
while IFS=: read -r usuario _ uid _ _ home shell; do
    [[ "${uid}" -lt 1000 ]] && continue    # Saltar usuarios del sistema
    [[ "${shell}" == */false || "${shell}" == */nologin ]] && continue

    CRON_USUARIO=$(crontab -l -u "${usuario}" 2>/dev/null | grep -v "^#" | grep -v "^$")
    if [[ -n "${CRON_USUARIO}" ]]; then
        warn "Usuario '${usuario}' tiene cron jobs activos:"
        echo "${CRON_USUARIO}" | while IFS= read -r tarea; do
            echo -e "    ${AMARILLO}${tarea}${NC}"
            # Detectar descarga o ejecución remota en cron
            if echo "${tarea}" | grep -qiE 'curl|wget|bash.*http|python.*http'; then
                crit "  ALERTA: cron job descarga o ejecuta código remoto"
            fi
        done
        ENCONTRADO_CRON_USER=true
    fi
done < /etc/passwd

[[ "${ENCONTRADO_CRON_USER}" == false ]] && \
    ok "Sin cron jobs configurados por usuarios del sistema"

# /var/spool/cron (Debian/Ubuntu)
if [[ -d /var/spool/cron/crontabs ]]; then
    ARCHIVOS_SPOOL=$(ls /var/spool/cron/crontabs/ 2>/dev/null | wc -l)
    if [[ "${ARCHIVOS_SPOOL}" -gt 0 ]]; then
        info "Archivos en /var/spool/cron/crontabs: $(ls /var/spool/cron/crontabs/ 2>/dev/null | tr '\n' ' ')"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 5. SERVICIOS ESCUCHANDO EN SOCKETS UNIX
# ══════════════════════════════════════════════════════════════════════════════
seccion "Sockets Unix con escritura pública"
echo ""

SOCKETS_PELIGROSOS=false
if command -v ss &>/dev/null; then
    ss -xlp 2>/dev/null | awk '{print $5}' | grep "/" | while IFS= read -r socket; do
        [[ -S "${socket}" ]] || continue
        PERM=$(stat -c "%a" "${socket}" 2>/dev/null)
        OWNER=$(stat -c "%U" "${socket}" 2>/dev/null)

        # Sockets con escritura para todos (world-writable)
        if [[ "${PERM}" =~ [0-7][0-7][2367] ]]; then
            warn "Socket Unix world-writable: ${socket} (${PERM}, propietario: ${OWNER})"
            SOCKETS_PELIGROSOS=true
        fi
    done
fi

[[ "${SOCKETS_PELIGROSOS}" == false ]] && \
    ok "Sin sockets Unix con permisos excesivos detectados"

# ── Resumen ───────────────────────────────────────────────────────────────────
resumen_modulo "Servicios"
