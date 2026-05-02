"""
Constantes del proyecto: colores de marca, esquema de tabla, configuración.
"""

# ── Colores de marca ─────────────────────────────────────────
DARK = "#1b1b1e"
GREEN = "#62b22f"
GREEN_LIGHT = "#7acc4a"
GREEN_DARK = "#4a8a1f"
GRAY = "#2a2a2e"
GRAY_LIGHT = "#3a3a3e"
WHITE = "#f0f0f0"
RED = "#e74c3c"
AMBER = "#f39c12"

# ── Tabla ────────────────────────────────────────────────────
NOMBRE_TABLA = "inventarios"

# ── Esquema esperado (nombres tras .lower() del Excel) ───────
COLUMNAS_ESQUEMA = [
    "fecha", "proveedor", "clasificacion", "sub_clasificacion",
    "codigo_de_barras_padre", "item", "clase_de_mercaderia",
    "tamanio", "acabado", "unidades_de_manejo",
    "inventario_cd_en_unidades", "inventario_cd_en_cajas", "transito",
]

COLUMNAS_NUMERICAS = [
    "codigo_de_barras_padre", "unidades_de_manejo",
    "inventario_cd_en_unidades", "inventario_cd_en_cajas", "transito",
]

COLUMNAS_TEXTO = [
    "proveedor", "clasificacion", "sub_clasificacion",
    "item", "clase_de_mercaderia", "tamanio", "acabado",
]

# ── Marcas Karayte (para filtro de marca) ────────────────────
MARCAS_KARAYTE = [
    "KARAY",
    "SG",
    "LO.",
    "EL ARTESANAL",
    "SX.",
    "KLIK GIN TONIC",
    "ESY",
    "OMEGASOL",
]

# ── Plotly ───────────────────────────────────────────────────
PLOTLY_COLORS = [GREEN, GREEN_LIGHT, "#3498db", AMBER, RED, "#9b59b6", "#1abc9c"]
