#!/usr/bin/env bash
# =============================================================================
# check_ssh.sh — Auditoría completa de configuración SSH
#
# Comprueba 20+ parámetros de seguridad del servidor SSH según:
#   - CIS Benchmark for Linux
#   - NIST SP 800-53
#   - Guía CCN-CERT del Esquema Nacional de Seguridad (ENS)
#
# Uso: bash check_ssh.sh
# =============================================================================

source "$(dirname "$0")/lib_comun.sh"

SSH_CONFIG="/etc/ssh/sshd_config"
SSH_CONFIG_DIR="/etc/ssh/sshd_config.d"

log_inicio_modulo "SSH"
titulo "AUDITORÍA DE CONFIGURACIÓN SSH"

# ── Verificar que existe sshd ─────────────────────────────────────────────────
if ! command -v sshd &>/dev/null; then
    warn "sshd no está instalado — módulo SSH omitido"
    exit 0
fi

if [[ ! -f "${SSH_CONFIG}" ]]; then
    crit "Archivo de configuración SSH no encontrado: ${SSH_CONFIG}"
    exit 1
fi

info "Configuración SSH: ${SSH_CONFIG}"
info "Versión sshd: $(sshd -V 2>&1 | head -1)"
echo ""

# ── Función: leer valor de parámetro SSH ──────────────────────────────────────
# Busca en sshd_config y en los archivos Include (sshd_config.d/*.conf)
leer_param() {
    local param="$1"
    local valor=""

    # Buscar en archivo principal (ignorar comentarios y mayúsculas/minúsculas)
    valor=$(grep -iE "^[[:space:]]*${param}[[:space:]]+" "${SSH_CONFIG}" 2>/dev/null \
            | tail -1 | awk '{print $2}')

    # Si no está en el principal, buscar en includes
    if [[ -z "${valor}" && -d "${SSH_CONFIG_DIR}" ]]; then
        valor=$(grep -rhiE "^[[:space:]]*${param}[[:space:]]+" "${SSH_CONFIG_DIR}"/*.conf 2>/dev/null \
                | tail -1 | awk '{print $2}')
    fi

    echo "${valor}"
}

# ── Función genérica de comprobación ─────────────────────────────────────────
# Uso: check_param "Nombre" "Parametro" "ValorEsperado" "ok_msg" "fail_msg" [critico]
check_param() {
    local descripcion="$1"
    local param="$2"
    local esperado="$3"
    local msg_ok="$4"
    local msg_fail="$5"
    local es_critico="${6:-no}"

    local actual
    actual=$(leer_param "${param}" | tr '[:upper:]' '[:lower:]')

    if [[ "${actual}" == "${esperado,,}" ]]; then
        ok "${msg_ok}"
    elif [[ -z "${actual}" ]]; then
        # Parámetro no definido — usar default del sistema
        warn "${descripcion}: no definido en config (default puede ser inseguro)"
    else
        if [[ "${es_critico}" == "si" ]]; then
            crit "${msg_fail} (actual: ${actual})"
        else
            warn "${msg_fail} (actual: ${actual})"
        fi
    fi
}

# ══════════════════════════════════════════════════════════════════════════════
# 1. ACCESO Y AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════════════════
seccion "Acceso y Autenticación"
echo ""

# PermitRootLogin — CRÍTICO
PERMIT_ROOT=$(leer_param "PermitRootLogin" | tr '[:upper:]' '[:lower:]')
case "${PERMIT_ROOT}" in
    "no")
        ok "PermitRootLogin = no — acceso root por SSH deshabilitado" ;;
    "prohibit-password"|"without-password")
        warn "PermitRootLogin = ${PERMIT_ROOT} — root puede acceder con clave pública" ;;
    "yes"|"")
        crit "PermitRootLogin = ${PERMIT_ROOT:-yes(default)} — root puede acceder con contraseña" ;;
    *)
        warn "PermitRootLogin = ${PERMIT_ROOT} — valor no estándar, revisar" ;;
esac

# PasswordAuthentication — CRÍTICO
check_param "PasswordAuthentication" "PasswordAuthentication" "no" \
    "PasswordAuthentication = no — solo se permite clave pública" \
    "PasswordAuthentication habilitado — fuerza bruta posible" \
    "si"

# PubkeyAuthentication
check_param "PubkeyAuthentication" "PubkeyAuthentication" "yes" \
    "PubkeyAuthentication = yes — autenticación por clave habilitada" \
    "PubkeyAuthentication deshabilitado — solo queda contraseña"

# ChallengeResponseAuthentication / KbdInteractiveAuthentication
CHAL=$(leer_param "ChallengeResponseAuthentication")
KBD=$(leer_param "KbdInteractiveAuthentication")
if [[ "${CHAL,,}" == "no" || "${KBD,,}" == "no" ]]; then
    ok "Autenticación por challenge-response deshabilitada"
else
    warn "ChallengeResponseAuthentication podría estar habilitada — revisar"
fi

# PermitEmptyPasswords
check_param "PermitEmptyPasswords" "PermitEmptyPasswords" "no" \
    "PermitEmptyPasswords = no — contraseñas vacías no permitidas" \
    "PermitEmptyPasswords habilitado — RIESGO CRITICO" \
    "si"

# UsePAM
PAM_VAL=$(leer_param "UsePAM" | tr '[:upper:]' '[:lower:]')
if [[ "${PAM_VAL}" == "yes" ]]; then
    ok "UsePAM = yes — autenticación PAM activa (mayor control)"
else
    warn "UsePAM = ${PAM_VAL:-no} — PAM deshabilitado, se pierde control de sesiones"
fi

# MaxAuthTries
MAX_AUTH=$(leer_param "MaxAuthTries")
if [[ -n "${MAX_AUTH}" ]]; then
    if [[ "${MAX_AUTH}" -le 3 ]]; then
        ok "MaxAuthTries = ${MAX_AUTH} — protección contra fuerza bruta"
    elif [[ "${MAX_AUTH}" -le 6 ]]; then
        warn "MaxAuthTries = ${MAX_AUTH} — recomendado <= 3"
    else
        crit "MaxAuthTries = ${MAX_AUTH} — demasiados intentos permitidos"
    fi
else
    warn "MaxAuthTries no definido (default = 6) — recomendado 3"
fi

# LoginGraceTime
GRACE=$(leer_param "LoginGraceTime")
if [[ -n "${GRACE}" ]]; then
    # Eliminar sufijo 'm' o 's'
    GRACE_NUM=$(echo "${GRACE}" | tr -d 'ms')
    if   [[ "${GRACE_NUM}" -le 30 ]]; then ok "LoginGraceTime = ${GRACE} — correcto"
    elif [[ "${GRACE_NUM}" -le 60 ]]; then warn "LoginGraceTime = ${GRACE} — recomendado <= 30s"
    else                                    crit "LoginGraceTime = ${GRACE} — demasiado tiempo para autenticarse"
    fi
else
    warn "LoginGraceTime no definido (default = 120s) — reducir a 30s"
fi

# ══════════════════════════════════════════════════════════════════════════════
# 2. PUERTO Y RED
# ══════════════════════════════════════════════════════════════════════════════
seccion "Puerto y configuración de red"
echo ""

# Puerto SSH
PUERTO_SSH=$(leer_param "Port")
PUERTO_SSH=${PUERTO_SSH:-22}
if [[ "${PUERTO_SSH}" == "22" ]]; then
    warn "Puerto SSH = 22 (estándar) — considerar cambiar para reducir ruido de bots"
else
    ok "Puerto SSH = ${PUERTO_SSH} (no estándar) — reduce intentos automatizados"
fi

# AddressFamily
ADDR_FAMILY=$(leer_param "AddressFamily" | tr '[:upper:]' '[:lower:]')
case "${ADDR_FAMILY}" in
    "inet")  ok "AddressFamily = inet — solo IPv4 habilitado" ;;
    "inet6") info "AddressFamily = inet6 — solo IPv6" ;;
    "any"|"") warn "AddressFamily = any (default) — escucha en IPv4 e IPv6" ;;
esac

# ListenAddress
LISTEN_ADDR=$(leer_param "ListenAddress")
if [[ -n "${LISTEN_ADDR}" && "${LISTEN_ADDR}" != "0.0.0.0" && "${LISTEN_ADDR}" != "::" ]]; then
    ok "ListenAddress = ${LISTEN_ADDR} — SSH enlazado a interfaz específica"
else
    warn "ListenAddress = ${LISTEN_ADDR:-0.0.0.0} — SSH escucha en todas las interfaces"
fi

# AllowUsers / AllowGroups — restricción de usuarios
ALLOW_USERS=$(leer_param "AllowUsers")
ALLOW_GROUPS=$(leer_param "AllowGroups")
DENY_USERS=$(leer_param "DenyUsers")

if [[ -n "${ALLOW_USERS}" ]]; then
    ok "AllowUsers definido: ${ALLOW_USERS}"
elif [[ -n "${ALLOW_GROUPS}" ]]; then
    ok "AllowGroups definido: ${ALLOW_GROUPS}"
else
    warn "AllowUsers/AllowGroups no definido — cualquier usuario válido puede conectar"
fi

if [[ -n "${DENY_USERS}" ]]; then
    ok "DenyUsers definido: ${DENY_USERS}"
fi

# MaxSessions
MAX_SESS=$(leer_param "MaxSessions")
if [[ -n "${MAX_SESS}" ]]; then
    if [[ "${MAX_SESS}" -le 4 ]]; then ok "MaxSessions = ${MAX_SESS}"
    else warn "MaxSessions = ${MAX_SESS} — considera reducirlo a 4"
    fi
else
    warn "MaxSessions no definido (default = 10)"
fi

# MaxStartups — protección contra DoS de conexiones SSH
MAXSTARTUPS=$(leer_param "MaxStartups")
if [[ -n "${MAXSTARTUPS}" ]]; then
    ok "MaxStartups = ${MAXSTARTUPS} — protección contra flood de conexiones"
else
    warn "MaxStartups no definido (default = 10:30:100) — considerar 10:30:60"
fi

# ══════════════════════════════════════════════════════════════════════════════
# 3. CIFRADO Y ALGORITMOS CRIPTOGRÁFICOS
# ══════════════════════════════════════════════════════════════════════════════
seccion "Algoritmos criptográficos"
echo ""

# Ciphers — algoritmos de cifrado simétrico
CIPHERS=$(leer_param "Ciphers")
if [[ -n "${CIPHERS}" ]]; then
    # Detectar algoritmos débiles
    if echo "${CIPHERS}" | grep -qiE 'arcfour|blowfish|cast128|3des|rc4'; then
        crit "Ciphers contiene algoritmos débiles: ${CIPHERS}"
    elif echo "${CIPHERS}" | grep -qiE 'aes128-ctr|aes256-ctr|aes128-gcm|aes256-gcm|chacha20'; then
        ok "Ciphers configurados correctamente: solo algoritmos fuertes"
    else
        warn "Ciphers = ${CIPHERS} — verificar manualmente"
    fi
else
    info "Ciphers no definido — usando defaults del sistema OpenSSH"
fi

# MACs — Message Authentication Codes
MACS=$(leer_param "MACs")
if [[ -n "${MACS}" ]]; then
    if echo "${MACS}" | grep -qiE 'md5|sha1(-96)?[^0-9]'; then
        crit "MACs contiene algoritmos débiles (MD5/SHA1): ${MACS}"
    else
        ok "MACs configurados: sin algoritmos débiles detectados"
    fi
else
    info "MACs no definido — usando defaults del sistema"
fi

# KexAlgorithms — intercambio de claves
KEX=$(leer_param "KexAlgorithms")
if [[ -n "${KEX}" ]]; then
    if echo "${KEX}" | grep -qiE 'diffie-hellman-group1|diffie-hellman-group14-sha1'; then
        crit "KexAlgorithms contiene DH débiles — riesgo de Logjam attack"
    else
        ok "KexAlgorithms sin algoritmos débiles detectados"
    fi
else
    info "KexAlgorithms no definido — usando defaults"
fi

# Protocol — solo SSHv2
PROTO=$(leer_param "Protocol")
if [[ -n "${PROTO}" ]]; then
    if [[ "${PROTO}" == "2" ]]; then
        ok "Protocol = 2 — SSHv1 deshabilitado"
    elif echo "${PROTO}" | grep -q "1"; then
        crit "Protocol incluye SSHv1 — VULNERABLE, deshabilitar inmediatamente"
    fi
else
    ok "Protocol no definido — OpenSSH moderno usa solo SSHv2 por defecto"
fi

# ══════════════════════════════════════════════════════════════════════════════
# 4. SESIONES Y FUNCIONALIDADES
# ══════════════════════════════════════════════════════════════════════════════
seccion "Sesiones y funcionalidades"
echo ""

# ClientAliveInterval y ClientAliveCountMax — timeout de sesión
ALIVE_INT=$(leer_param "ClientAliveInterval")
ALIVE_MAX=$(leer_param "ClientAliveCountMax")

if [[ -n "${ALIVE_INT}" && "${ALIVE_INT}" -gt 0 ]]; then
    TIMEOUT_TOTAL=$(( ALIVE_INT * ${ALIVE_MAX:-3} ))
    if [[ "${TIMEOUT_TOTAL}" -le 900 ]]; then
        ok "Timeout de sesión inactiva: ${TIMEOUT_TOTAL}s (${ALIVE_INT}s × ${ALIVE_MAX:-3})"
    else
        warn "Timeout de sesión muy largo: ${TIMEOUT_TOTAL}s — reducir ClientAliveInterval"
    fi
else
    warn "ClientAliveInterval = 0 — sesiones inactivas no se cierran automáticamente"
fi

# X11Forwarding — reenvío gráfico
check_param "X11Forwarding" "X11Forwarding" "no" \
    "X11Forwarding = no — reenvío X11 deshabilitado" \
    "X11Forwarding habilitado — riesgo si el cliente X11 es malicioso"

# AllowTcpForwarding — túneles TCP
TCP_FWD=$(leer_param "AllowTcpForwarding" | tr '[:upper:]' '[:lower:]')
case "${TCP_FWD}" in
    "no")     ok "AllowTcpForwarding = no — túneles TCP deshabilitados" ;;
    "local")  warn "AllowTcpForwarding = local — solo túneles locales permitidos" ;;
    "yes"|"") warn "AllowTcpForwarding = ${TCP_FWD:-yes} — túneles TCP permitidos (puede usarse para evadir firewalls)" ;;
esac

# GatewayPorts
check_param "GatewayPorts" "GatewayPorts" "no" \
    "GatewayPorts = no — reenvío de puertos en todas las interfaces deshabilitado" \
    "GatewayPorts habilitado — puede exponer servicios internos"

# PermitTunnel
check_param "PermitTunnel" "PermitTunnel" "no" \
    "PermitTunnel = no — VPN sobre SSH deshabilitada" \
    "PermitTunnel habilitado — puede usarse para tunelización no autorizada"

# AllowAgentForwarding
check_param "AllowAgentForwarding" "AllowAgentForwarding" "no" \
    "AllowAgentForwarding = no — reenvío de agente SSH deshabilitado" \
    "AllowAgentForwarding habilitado — riesgo de secuestro de agente"

# PrintLastLog
check_param "PrintLastLog" "PrintLastLog" "yes" \
    "PrintLastLog = yes — se muestra último acceso al conectar" \
    "PrintLastLog = no — el usuario no ve cuándo fue su último acceso"

# Banner
BANNER=$(leer_param "Banner")
if [[ -n "${BANNER}" && "${BANNER}" != "none" ]]; then
    ok "Banner legal configurado: ${BANNER}"
else
    warn "Banner no configurado — recomendado por cumplimiento legal (RGPD/ENS)"
fi

# ══════════════════════════════════════════════════════════════════════════════
# 5. CLAVES AUTORIZADAS Y ARCHIVOS CRÍTICOS
# ══════════════════════════════════════════════════════════════════════════════
seccion "Archivos de claves y permisos"
echo ""

# Permisos del archivo sshd_config
PERM_CONFIG=$(stat -c "%a" "${SSH_CONFIG}" 2>/dev/null)
OWNER_CONFIG=$(stat -c "%U" "${SSH_CONFIG}" 2>/dev/null)

if [[ "${PERM_CONFIG}" == "600" || "${PERM_CONFIG}" == "640" ]]; then
    ok "sshd_config permisos = ${PERM_CONFIG} (propietario: ${OWNER_CONFIG})"
else
    crit "sshd_config permisos = ${PERM_CONFIG} — debería ser 600 ó 640"
fi

# Permisos de claves del host
for clave in /etc/ssh/ssh_host_*_key; do
    [[ -f "${clave}" ]] || continue
    PERM_CLAVE=$(stat -c "%a" "${clave}" 2>/dev/null)
    if [[ "${PERM_CLAVE}" == "600" ]]; then
        ok "Clave host ${clave##*/} — permisos correctos (600)"
    else
        crit "Clave host ${clave##*/} — permisos ${PERM_CLAVE} (debe ser 600)"
    fi
done

# Claves autorizadas con escritura para otros
info "Revisando authorized_keys con permisos excesivos..."
find /home -name "authorized_keys" 2>/dev/null | while read -r akf; do
    PERM_AK=$(stat -c "%a" "${akf}" 2>/dev/null)
    OWNER_AK=$(stat -c "%U" "${akf}" 2>/dev/null)
    if [[ "${PERM_AK}" =~ ^[0-7][0-7][1-7]$ ]]; then
        crit "${akf} — permisos ${PERM_AK}: escritura para 'others' — COMPROMISO POSIBLE"
    elif [[ "${PERM_AK}" =~ ^[0-7][1-7][0-7]$ ]]; then
        warn "${akf} — permisos ${PERM_AK}: escritura para 'group'"
    else
        ok "${akf} — permisos ${PERM_AK} correctos (propietario: ${OWNER_AK})"
    fi
done

# ══════════════════════════════════════════════════════════════════════════════
# 6. INTENTOS FALLIDOS RECIENTES (últimas 24h)
# ══════════════════════════════════════════════════════════════════════════════
seccion "Intentos de acceso SSH fallidos (últimas 24h)"
echo ""

LOG_SSHD=""
for posible_log in /var/log/auth.log /var/log/secure /var/log/syslog; do
    [[ -f "${posible_log}" ]] && LOG_SSHD="${posible_log}" && break
done

if [[ -n "${LOG_SSHD}" ]]; then
    # Contar fallos totales
    FALLOS=$(grep -c "Failed password\|Invalid user\|authentication failure" "${LOG_SSHD}" 2>/dev/null || echo 0)
    AYER=$(date -d "yesterday" '+%b %e' 2>/dev/null || date -v-1d '+%b %e' 2>/dev/null || echo "")

    if [[ "${FALLOS}" -eq 0 ]]; then
        ok "Sin intentos de acceso fallidos en ${LOG_SSHD}"
    elif [[ "${FALLOS}" -lt 50 ]]; then
        warn "${FALLOS} intentos fallidos de SSH — actividad normal-baja"
    elif [[ "${FALLOS}" -lt 500 ]]; then
        warn "${FALLOS} intentos fallidos — posible reconocimiento/fuerza bruta lenta"
    else
        crit "${FALLOS} intentos fallidos — ATAQUE DE FUERZA BRUTA EN CURSO o reciente"
    fi

    # Top IPs atacantes
    echo ""
    info "Top 5 IPs con más intentos fallidos:"
    grep "Failed password\|Invalid user" "${LOG_SSHD}" 2>/dev/null \
        | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' \
        | sort | uniq -c | sort -rn | head -5 \
        | while read -r count ip; do
            if   [[ "${count}" -gt 100 ]]; then
                echo -e "    ${ROJO}${count} intentos desde ${ip}${NC}"
            elif [[ "${count}" -gt 20 ]]; then
                echo -e "    ${AMARILLO}${count} intentos desde ${ip}${NC}"
            else
                echo -e "    ${GRIS}${count} intentos desde ${ip}${NC}"
            fi
        done

    # Usuarios inexistentes más atacados
    echo ""
    info "Top 5 usuarios inexistentes más probados:"
    grep "Invalid user" "${LOG_SSHD}" 2>/dev/null \
        | awk '{print $8}' \
        | sort | uniq -c | sort -rn | head -5 \
        | while read -r count usuario; do
            echo -e "    ${AMARILLO}${count}x${NC} usuario '${usuario}'"
        done
else
    warn "No se encontró log de autenticación (auth.log/secure) — revisar configuración de syslog"
fi

# ── Resumen ───────────────────────────────────────────────────────────────────
resumen_modulo "SSH"
