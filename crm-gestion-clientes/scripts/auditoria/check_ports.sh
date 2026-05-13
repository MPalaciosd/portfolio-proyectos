#!/usr/bin/env bash
# =============================================================================
# check_ports.sh — Auditoría de puertos abiertos
#
# Comprueba:
#   1. Puertos en escucha (IPv4 e IPv6)
#   2. Puertos peligrosos expuestos públicamente
#   3. Servicios desconocidos o sospechosos
#   4. Comparativa contra lista blanca de puertos permitidos
#
# Uso: bash check_ports.sh [--json]
# =============================================================================

source "$(dirname "$0")/lib_comun.sh"

# ── Lista blanca de puertos considerados seguros ──────────────────────────────
# Modificar según la política de seguridad del servidor
PUERTOS_PERMITIDOS=(22 80 443 25 587 465 993 995 3306 5432 6379)

# Puertos considerados peligrosos si están expuestos públicamente
declare -A PUERTOS_PELIGROSOS=(
    [21]="FTP (sin cifrar) — usar SFTP"
    [23]="Telnet (sin cifrar) — usar SSH"
    [25]="SMTP sin auth — riesgo de relay abierto"
    [53]="DNS — solo si es servidor DNS"
    [135]="RPC Windows — no debería estar en Linux"
    [137]="NetBIOS — potencial enumeración de red"
    [139]="NetBIOS Session — potencial enumeración"
    [445]="SMB — vector de ransomware frecuente"
    [1433]="MSSQL — exponer a internet es peligroso"
    [1521]="Oracle DB — no exponer a internet"
    [2049]="NFS — montar sistemas de archivos remotos"
    [3306]="MySQL — solo localhost a menos que sea necesario"
    [3389]="RDP — vector de ataque muy común"
    [4444]="Metasploit default — muy sospechoso"
    [5432]="PostgreSQL — solo localhost"
    [5900]="VNC — sin cifrar"
    [6379]="Redis — sin auth por defecto"
    [8080]="HTTP alternativo — revisar qué corre aquí"
    [27017]="MongoDB — sin auth por defecto en versiones antiguas"
)

log_inicio_modulo "PUERTOS"
titulo "AUDITORÍA DE PUERTOS"

# ── Función: obtener puertos en escucha ───────────────────────────────────────
obtener_puertos() {
    if requiere ss; then
        # ss es más moderno que netstat
        ss -tlnp 2>/dev/null
    elif requiere netstat; then
        netstat -tlnp 2>/dev/null
    else
        crit "No se encontró 'ss' ni 'netstat' — instala iproute2 o net-tools"
        return 1
    fi
}

# ── Función: extraer lista de puertos numéricos ───────────────────────────────
extraer_puertos_lista() {
    obtener_puertos | grep -E 'LISTEN|UNCONN' \
        | awk '{print $5}' \
        | grep -oE '[0-9]+$' \
        | sort -nu
}

# ══════════════════════════════════════════════════════════════════════════════
# 1. LISTADO COMPLETO DE PUERTOS EN ESCUCHA
# ══════════════════════════════════════════════════════════════════════════════
seccion "Puertos TCP en escucha"

if requiere ss; then
    echo ""
    echo -e "  ${GRIS}Proto  Local                   Proceso${NC}"
    echo    "  ─────────────────────────────────────────────────────"

    while IFS= read -r linea; do
        puerto=$(echo "${linea}" | awk '{print $5}' | grep -oE '[0-9]+$')
        proceso=$(echo "${linea}" | awk '{print $7}' | sed 's/users:((//' | sed 's/,.*//' | sed 's/"//')
        addr=$(echo "${linea}" | awk '{print $5}')
        proto=$(echo "${linea}" | awk '{print $1}')

        [[ -z "${puerto}" ]] && continue

        # Color según si es conocido o sospechoso
        if [[ -n "${PUERTOS_PELIGROSOS[${puerto}]}" ]]; then
            echo -e "  ${ROJO}${proto:-tcp}     ${addr:-?}$(printf '%*s' $((24 - ${#addr})) '') ${proceso:-?}${NC}"
        elif printf '%s\n' "${PUERTOS_PERMITIDOS[@]}" | grep -qx "${puerto}"; then
            echo -e "  ${VERDE}${proto:-tcp}     ${addr:-?}$(printf '%*s' $((24 - ${#addr})) '') ${proceso:-?}${NC}"
        else
            echo -e "  ${AMARILLO}${proto:-tcp}     ${addr:-?}$(printf '%*s' $((24 - ${#addr})) '') ${proceso:-?}${NC}"
        fi
    done < <(ss -tlnp 2>/dev/null | tail -n +2 | grep LISTEN)
fi

# ══════════════════════════════════════════════════════════════════════════════
# 2. DETECCIÓN DE PUERTOS PELIGROSOS
# ══════════════════════════════════════════════════════════════════════════════
seccion "Detección de puertos peligrosos"
echo ""

PUERTOS_ABIERTOS=$(extraer_puertos_lista)
ENCONTRADO_PELIGROSO=false

for puerto in "${!PUERTOS_PELIGROSOS[@]}"; do
    if echo "${PUERTOS_ABIERTOS}" | grep -qx "${puerto}"; then
        crit "Puerto ${puerto}/tcp ABIERTO — ${PUERTOS_PELIGROSOS[${puerto}]}"
        ENCONTRADO_PELIGROSO=true
    fi
done

if [[ "${ENCONTRADO_PELIGROSO}" == false ]]; then
    ok "No se detectaron puertos peligrosos conocidos en escucha"
fi

# ══════════════════════════════════════════════════════════════════════════════
# 3. PUERTOS FUERA DE LA LISTA BLANCA
# ══════════════════════════════════════════════════════════════════════════════
seccion "Puertos fuera de lista blanca"
echo ""

while IFS= read -r puerto; do
    [[ -z "${puerto}" ]] && continue
    if ! printf '%s\n' "${PUERTOS_PERMITIDOS[@]}" | grep -qx "${puerto}"; then
        if [[ -z "${PUERTOS_PELIGROSOS[${puerto}]}" ]]; then
            # No está en la lista blanca NI en la lista de peligrosos — revisar
            PROCESO=$(ss -tlnp 2>/dev/null | awk '{print $5, $7}' \
                | grep ":${puerto}" | head -1 | awk '{print $2}' \
                | sed 's/users:(("//' | sed 's/".*//')
            warn "Puerto ${puerto}/tcp no está en lista blanca — proceso: ${PROCESO:-desconocido}"
        fi
    fi
done <<< "${PUERTOS_ABIERTOS}"

# ══════════════════════════════════════════════════════════════════════════════
# 4. PUERTOS EN ESCUCHA EN TODAS LAS INTERFACES (0.0.0.0)
# ══════════════════════════════════════════════════════════════════════════════
seccion "Servicios expuestos en TODAS las interfaces (0.0.0.0)"
echo ""

EXPUESTO_PUBLICO=false
while IFS= read -r linea; do
    addr=$(echo "${linea}" | awk '{print $5}')
    puerto=$(echo "${linea}" | grep -oE ':([0-9]+)$' | tr -d ':')

    # 0.0.0.0 y :: significan que acepta conexiones desde cualquier IP
    if echo "${addr}" | grep -qE '^(0\.0\.0\.0|::)'; then
        [[ -z "${puerto}" ]] && continue
        PROCESO=$(echo "${linea}" | awk '{print $7}' | sed 's/users:(("//' | sed 's/".*//')

        if [[ "${puerto}" -gt 1024 ]]; then
            warn "Puerto ${puerto} expuesto públicamente en 0.0.0.0 — proceso: ${PROCESO:-?}"
        else
            info "Puerto ${puerto} expuesto públicamente (sistema) — proceso: ${PROCESO:-?}"
        fi
        EXPUESTO_PUBLICO=true
    fi
done < <(ss -tlnp 2>/dev/null | grep LISTEN)

if [[ "${EXPUESTO_PUBLICO}" == false ]]; then
    ok "Todos los servicios escuchan solo en localhost o interfaz específica"
fi

# ══════════════════════════════════════════════════════════════════════════════
# 5. SCAN RÁPIDO DE PUERTOS UDP CRÍTICOS
# ══════════════════════════════════════════════════════════════════════════════
seccion "Puertos UDP críticos"
echo ""

if requiere ss; then
    UDP_PUERTOS=$(ss -ulnp 2>/dev/null | awk '{print $5}' | grep -oE '[0-9]+$' | sort -nu)

    declare -A UDP_PELIGROSOS=(
        [69]="TFTP — transferencia sin autenticación"
        [111]="RPC portmapper"
        [161]="SNMP — community 'public' es peligroso"
        [1900]="UPnP — descubrimiento de red no seguro"
        [5353]="mDNS — puede filtrar información de red"
    )

    for puerto in "${!UDP_PELIGROSOS[@]}"; do
        if echo "${UDP_PUERTOS}" | grep -qx "${puerto}"; then
            warn "UDP ${puerto} abierto — ${UDP_PELIGROSOS[${puerto}]}"
        fi
    done
    ok "Comprobación de puertos UDP críticos completada"
fi

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GRIS}Total puertos TCP en escucha: $(echo "${PUERTOS_ABIERTOS}" | wc -l | tr -d ' ')${NC}"
resumen_modulo "Puertos"
