#!/usr/bin/env bash
# =============================================================================
# lib_comun.sh — Librería compartida de funciones para todos los scripts
# Importar con: source "$(dirname "$0")/lib_comun.sh"
# =============================================================================

# ── Colores ANSI ──────────────────────────────────────────────────────────────
ROJO='\033[0;31m'
VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
AZUL='\033[0;34m'
CYAN='\033[0;36m'
BLANCO='\033[1;37m'
GRIS='\033[0;37m'
NC='\033[0m'   # No Color

# ── Directorios del proyecto ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${PROYECTO_DIR}/logs/auditoria"
FECHA=$(date '+%Y-%m-%d')
HORA=$(date '+%H:%M:%S')
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')

mkdir -p "${LOG_DIR}"

# ── Contadores globales ───────────────────────────────────────────────────────
TOTAL_OK=0
TOTAL_WARN=0
TOTAL_CRIT=0

# ── Funciones de output ───────────────────────────────────────────────────────

titulo() {
    echo ""
    echo -e "${AZUL}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${AZUL}║${BLANCO}  $1${AZUL}$(printf '%*s' $((62 - ${#1})) '')║${NC}"
    echo -e "${AZUL}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

seccion() {
    echo ""
    echo -e "${CYAN}┌─ $1 $(printf '─%.0s' $(seq 1 $((58 - ${#1}))))┐${NC}"
}

ok() {
    echo -e "  ${VERDE}[OK]${NC}   $1"
    TOTAL_OK=$((TOTAL_OK + 1))
    log_resultado "OK" "$1"
}

warn() {
    echo -e "  ${AMARILLO}[WARN]${NC} $1"
    TOTAL_WARN=$((TOTAL_WARN + 1))
    log_resultado "WARN" "$1"
}

crit() {
    echo -e "  ${ROJO}[CRIT]${NC} $1"
    TOTAL_CRIT=$((TOTAL_CRIT + 1))
    log_resultado "CRIT" "$1"
}

info() {
    echo -e "  ${GRIS}[INFO]${NC} $1"
}

# ── Logging a archivo ─────────────────────────────────────────────────────────
LOG_FILE="${LOG_DIR}/audit_${FECHA}.log"

log_resultado() {
    local nivel="$1"
    local mensaje="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${nivel}] ${mensaje}" >> "${LOG_FILE}"
}

log_inicio_modulo() {
    local modulo="$1"
    echo "" >> "${LOG_FILE}"
    echo "## MÓDULO: ${modulo} — $(date '+%Y-%m-%d %H:%M:%S')" >> "${LOG_FILE}"
}

# ── Detección del sistema operativo ──────────────────────────────────────────
detectar_os() {
    if   [[ -f /etc/debian_version ]]; then echo "debian"
    elif [[ -f /etc/redhat-release ]]; then echo "redhat"
    elif [[ -f /etc/arch-release   ]]; then echo "arch"
    elif [[ "$(uname)" == "Darwin" ]];  then echo "macos"
    else                                     echo "unknown"
    fi
}

OS=$(detectar_os)

# ── Comprobador de herramientas ───────────────────────────────────────────────
requiere() {
    local cmd="$1"
    if ! command -v "${cmd}" &>/dev/null; then
        warn "Herramienta '${cmd}' no disponible — comprobación omitida"
        return 1
    fi
    return 0
}

# ── Resumen final del módulo ──────────────────────────────────────────────────
resumen_modulo() {
    local modulo="$1"
    echo ""
    echo -e "${GRIS}  Resumen ${modulo}: ${VERDE}${TOTAL_OK} OK${NC} | ${AMARILLO}${TOTAL_WARN} WARN${NC} | ${ROJO}${TOTAL_CRIT} CRIT${NC}"
    echo ""
}
