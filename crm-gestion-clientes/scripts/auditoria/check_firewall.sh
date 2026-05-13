#!/usr/bin/env bash
# =============================================================================
# check_firewall.sh — Auditoría completa del firewall
#
# Soporta: ufw, iptables, nftables, firewalld
# Comprueba:
#   1. Qué firewall está activo
#   2. Política por defecto (DROP vs ACCEPT)
#   3. Reglas actuales y posibles gaps
#   4. Protecciones específicas (SYN flood, ICMP, spoofing)
#   5. Persistencia de reglas tras reinicio
#
# Uso: bash check_firewall.sh
# =============================================================================

source "$(dirname "$0")/lib_comun.sh"

log_inicio_modulo "FIREWALL"
titulo "AUDITORÍA DE FIREWALL"

FIREWALL_ACTIVO="ninguno"

# ══════════════════════════════════════════════════════════════════════════════
# 1. DETECCIÓN DEL FIREWALL ACTIVO
# ══════════════════════════════════════════════════════════════════════════════
seccion "Detección del firewall"
echo ""

# UFW
if command -v ufw &>/dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null | head -1)
    if echo "${UFW_STATUS}" | grep -qi "active"; then
        ok "UFW activo: ${UFW_STATUS}"
        FIREWALL_ACTIVO="ufw"
    else
        warn "UFW instalado pero INACTIVO: ${UFW_STATUS}"
    fi
fi

# firewalld
if command -v firewall-cmd &>/dev/null; then
    if systemctl is-active --quiet firewalld 2>/dev/null; then
        ok "firewalld activo"
        ZONA=$(firewall-cmd --get-default-zone 2>/dev/null)
        info "Zona por defecto: ${ZONA}"
        FIREWALL_ACTIVO="firewalld"
    else
        warn "firewalld instalado pero inactivo"
    fi
fi

# iptables
if command -v iptables &>/dev/null; then
    IPT_RULES=$(iptables -L 2>/dev/null | grep -c "^[A-Z]" || echo 0)
    if [[ "${IPT_RULES}" -gt 3 ]]; then   # más de las 3 cadenas vacías por defecto
        info "iptables tiene ${IPT_RULES} cadenas/reglas definidas"
        [[ "${FIREWALL_ACTIVO}" == "ninguno" ]] && FIREWALL_ACTIVO="iptables"
    fi
fi

# nftables
if command -v nft &>/dev/null; then
    NFT_RULES=$(nft list ruleset 2>/dev/null | wc -l)
    if [[ "${NFT_RULES}" -gt 5 ]]; then
        info "nftables tiene reglas definidas (${NFT_RULES} líneas)"
        [[ "${FIREWALL_ACTIVO}" == "ninguno" ]] && FIREWALL_ACTIVO="nftables"
    fi
fi

if [[ "${FIREWALL_ACTIVO}" == "ninguno" ]]; then
    crit "NO SE DETECTÓ NINGÚN FIREWALL ACTIVO — servidor completamente expuesto"
    echo ""
    echo -e "  ${ROJO}  Para activar ufw:${NC}"
    echo    "    sudo apt install ufw"
    echo    "    sudo ufw default deny incoming"
    echo    "    sudo ufw default allow outgoing"
    echo    "    sudo ufw allow ssh"
    echo    "    sudo ufw enable"
    echo ""
fi

# ══════════════════════════════════════════════════════════════════════════════
# 2. AUDITORÍA UFW
# ══════════════════════════════════════════════════════════════════════════════
if [[ "${FIREWALL_ACTIVO}" == "ufw" ]]; then
    seccion "Reglas UFW"
    echo ""

    # Política por defecto
    UFW_DEFAULT_IN=$(ufw status verbose 2>/dev/null | grep "Default:" | grep -oiE 'deny|allow|reject' | head -1)
    UFW_DEFAULT_OUT=$(ufw status verbose 2>/dev/null | grep "Default:" | awk '{print $4}' | tr -d '()')

    if [[ "${UFW_DEFAULT_IN,,}" == "deny" || "${UFW_DEFAULT_IN,,}" == "reject" ]]; then
        ok "Política INCOMING por defecto: ${UFW_DEFAULT_IN^^} — tráfico bloqueado salvo excepciones"
    else
        crit "Política INCOMING por defecto: ${UFW_DEFAULT_IN^^} — todo el tráfico entrante permitido"
    fi

    if [[ "${UFW_DEFAULT_OUT,,}" == "allow" ]]; then
        ok "Política OUTGOING por defecto: ALLOW — tráfico saliente permitido"
    else
        warn "Política OUTGOING: ${UFW_DEFAULT_OUT} — verificar que no bloquea servicios necesarios"
    fi

    # Listar reglas activas
    echo ""
    info "Reglas UFW activas:"
    ufw status numbered 2>/dev/null | grep -E '^\[' | while IFS= read -r regla; do
        puerto=$(echo "${regla}" | grep -oE '[0-9]+(/tcp|/udp)?' | head -1)
        accion=$(echo "${regla}" | grep -oiE 'ALLOW|DENY|REJECT|LIMIT' | head -1)

        case "${accion}" in
            "ALLOW") echo -e "  ${VERDE}  ${regla}${NC}" ;;
            "DENY"|"REJECT") echo -e "  ${ROJO}  ${regla}${NC}" ;;
            "LIMIT") echo -e "  ${CYAN}  ${regla}${NC}" ;;
            *)        echo    "    ${regla}" ;;
        esac
    done

    # Verificar si SSH tiene rate limiting
    if ufw status 2>/dev/null | grep -qiE 'ssh|22.*LIMIT|LIMIT.*22'; then
        ok "SSH tiene rate limiting (LIMIT) — protección anti-fuerza bruta activa"
    else
        warn "SSH no tiene rate limiting — considera: ufw limit ssh"
    fi

    # Verificar reglas IPv6
    if ufw status verbose 2>/dev/null | grep -qi "ipv6.*enabled"; then
        ok "IPv6 habilitado en UFW — reglas aplican también a IPv6"
    else
        warn "IPv6 no habilitado en UFW — posible bypass a través de IPv6"
    fi

    # Logging
    UFW_LOG=$(ufw status verbose 2>/dev/null | grep "Logging:" | awk '{print $2}')
    if [[ "${UFW_LOG,,}" != "off" && -n "${UFW_LOG}" ]]; then
        ok "UFW logging = ${UFW_LOG} — actividad del firewall registrada"
    else
        warn "UFW logging = off — ningún intento bloqueado queda registrado"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 3. AUDITORÍA IPTABLES
# ══════════════════════════════════════════════════════════════════════════════
if command -v iptables &>/dev/null; then
    seccion "Políticas iptables (tabla filter)"
    echo ""

    # Política de las 3 cadenas principales
    while IFS= read -r linea; do
        cadena=$(echo "${linea}" | awk '{print $1}')
        politica=$(echo "${linea}" | awk '{print $2}' | tr -d '()')

        case "${politica}" in
            "DROP"|"REJECT")
                ok "Cadena ${cadena}: política ${politica} — tráfico bloqueado por defecto" ;;
            "ACCEPT")
                if [[ "${cadena}" == "INPUT" || "${cadena}" == "FORWARD" ]]; then
                    crit "Cadena ${cadena}: política ACCEPT — todo el tráfico permitido por defecto"
                else
                    ok "Cadena ${cadena}: política ACCEPT — tráfico saliente permitido"
                fi ;;
        esac
    done < <(iptables -L 2>/dev/null | grep "^Chain" | grep -E "INPUT|OUTPUT|FORWARD")

    # Número de reglas
    TOTAL_REGLAS=$(iptables -L 2>/dev/null | grep -c "^[A-Z]" || echo 0)
    info "Total reglas en iptables: ${TOTAL_REGLAS}"

    # Comprobaciones específicas de seguridad
    echo ""
    info "Comprobaciones de protecciones específicas:"

    # Protección SYN flood
    if iptables -L 2>/dev/null | grep -q "SYN\|SYNFLOOD\|--syn"; then
        ok "Regla anti-SYN flood detectada"
    else
        warn "Sin protección SYN flood en iptables — añadir limite de SYN por segundo"
    fi

    # Protección INVALID packets
    if iptables -L 2>/dev/null | grep -q "INVALID"; then
        ok "Paquetes INVALID descartados"
    else
        warn "Sin regla para paquetes INVALID — considerar: -m state --state INVALID -j DROP"
    fi

    # Loopback permitido
    if iptables -L 2>/dev/null | grep -qE "ACCEPT.*lo|lo.*ACCEPT"; then
        ok "Interfaz loopback (lo) permitida"
    else
        warn "Interfaz loopback podría estar bloqueada — revisar"
    fi

    # Conexiones establecidas permitidas
    if iptables -L 2>/dev/null | grep -qE "ESTABLISHED|RELATED"; then
        ok "Conexiones ESTABLISHED/RELATED permitidas — tráfico de respuesta OK"
    else
        warn "Sin regla ESTABLISHED/RELATED — el tráfico de respuesta podría bloquearse"
    fi

    # ── Verificar persistencia iptables ──────────────────────────────────────
    echo ""
    seccion "Persistencia de reglas iptables"
    echo ""

    PERSISTENCIA_OK=false
    for herramienta in iptables-save iptables-persistent netfilter-persistent; do
        if command -v "${herramienta}" &>/dev/null; then
            ok "Herramienta de persistencia disponible: ${herramienta}"
            PERSISTENCIA_OK=true
        fi
    done

    # Verificar si hay archivo de reglas guardadas
    for ruta_reglas in /etc/iptables/rules.v4 /etc/iptables.rules /etc/sysconfig/iptables; do
        if [[ -f "${ruta_reglas}" ]]; then
            MTIME=$(stat -c "%y" "${ruta_reglas}" 2>/dev/null | cut -d' ' -f1)
            ok "Reglas guardadas en ${ruta_reglas} (actualizado: ${MTIME})"
            PERSISTENCIA_OK=true
        fi
    done

    if [[ "${PERSISTENCIA_OK}" == false ]]; then
        crit "Las reglas iptables NO persisten tras reinicio — usar iptables-persistent"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 4. AUDITORÍA FIREWALLD
# ══════════════════════════════════════════════════════════════════════════════
if [[ "${FIREWALL_ACTIVO}" == "firewalld" ]]; then
    seccion "Configuración firewalld"
    echo ""

    ZONA_DEFAULT=$(firewall-cmd --get-default-zone 2>/dev/null)
    info "Zona por defecto: ${ZONA_DEFAULT}"

    # Servicios permitidos en la zona por defecto
    SERVICIOS_FW=$(firewall-cmd --zone="${ZONA_DEFAULT}" --list-services 2>/dev/null)
    info "Servicios permitidos en zona ${ZONA_DEFAULT}: ${SERVICIOS_FW}"

    # Puertos directos
    PUERTOS_FW=$(firewall-cmd --zone="${ZONA_DEFAULT}" --list-ports 2>/dev/null)
    if [[ -n "${PUERTOS_FW}" ]]; then
        warn "Puertos directos abiertos: ${PUERTOS_FW} — revisar si son necesarios todos"
    else
        ok "Sin puertos directos adicionales — todo gestionado por servicios"
    fi

    # Política de la zona
    TARGET=$(firewall-cmd --zone="${ZONA_DEFAULT}" --query-target 2>/dev/null || echo "default")
    info "Target de la zona: ${TARGET}"

    # Rich rules
    RICH=$(firewall-cmd --zone="${ZONA_DEFAULT}" --list-rich-rules 2>/dev/null)
    if [[ -n "${RICH}" ]]; then
        info "Rich rules activas:"
        echo "${RICH}" | while read -r regla; do
            echo "    ${regla}"
        done
    fi

    # Panic mode
    if firewall-cmd --query-panic 2>/dev/null | grep -q "yes"; then
        crit "PANIC MODE ACTIVO — todo el tráfico bloqueado"
    else
        ok "Panic mode inactivo — funcionamiento normal"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 5. PROTECCIONES DEL KERNEL (sysctl)
# ══════════════════════════════════════════════════════════════════════════════
seccion "Protecciones de red del kernel (sysctl)"
echo ""

declare -A SYSCTL_ESPERADOS=(
    ["net.ipv4.ip_forward"]="0"
    ["net.ipv4.conf.all.accept_redirects"]="0"
    ["net.ipv4.conf.default.accept_redirects"]="0"
    ["net.ipv4.conf.all.send_redirects"]="0"
    ["net.ipv4.conf.all.accept_source_route"]="0"
    ["net.ipv4.conf.all.log_martians"]="1"
    ["net.ipv4.icmp_echo_ignore_broadcasts"]="1"
    ["net.ipv4.icmp_ignore_bogus_error_responses"]="1"
    ["net.ipv4.tcp_syncookies"]="1"
    ["net.ipv6.conf.all.accept_redirects"]="0"
    ["net.ipv6.conf.all.accept_source_route"]="0"
)

declare -A SYSCTL_DESC=(
    ["net.ipv4.ip_forward"]="Reenvío de paquetes IP (router) — debe ser 0 salvo NAT"
    ["net.ipv4.conf.all.accept_redirects"]="Aceptar ICMP redirects — vector de MITM"
    ["net.ipv4.conf.default.accept_redirects"]="Aceptar ICMP redirects (default)"
    ["net.ipv4.conf.all.send_redirects"]="Enviar ICMP redirects — solo en routers"
    ["net.ipv4.conf.all.accept_source_route"]="Source routing — obsoleto y peligroso"
    ["net.ipv4.conf.all.log_martians"]="Loguear paquetes con IPs imposibles (martians)"
    ["net.ipv4.icmp_echo_ignore_broadcasts"]="Ignorar ICMP broadcast — anti-Smurf"
    ["net.ipv4.icmp_ignore_bogus_error_responses"]="Ignorar respuestas ICMP falsas"
    ["net.ipv4.tcp_syncookies"]="SYN cookies — protección anti-SYN flood"
    ["net.ipv6.conf.all.accept_redirects"]="ICMP redirects IPv6 — vector MITM"
    ["net.ipv6.conf.all.accept_source_route"]="Source routing IPv6 — peligroso"
)

for param in "${!SYSCTL_ESPERADOS[@]}"; do
    valor_actual=$(sysctl -n "${param}" 2>/dev/null)
    valor_esperado="${SYSCTL_ESPERADOS[${param}]}"
    desc="${SYSCTL_DESC[${param}]}"

    if [[ -z "${valor_actual}" ]]; then
        warn "${param}: no disponible en este sistema"
    elif [[ "${valor_actual}" == "${valor_esperado}" ]]; then
        ok "${param} = ${valor_actual} — ${desc}"
    else
        if [[ "${param}" == "net.ipv4.tcp_syncookies" || \
              "${param}" == "net.ipv4.icmp_echo_ignore_broadcasts" ]]; then
            crit "${param} = ${valor_actual} (esperado: ${valor_esperado}) — ${desc}"
        else
            warn "${param} = ${valor_actual} (esperado: ${valor_esperado}) — ${desc}"
        fi
    fi
done

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GRIS}Firewall activo: ${BLANCO}${FIREWALL_ACTIVO}${NC}"
resumen_modulo "Firewall"
