"""Rutas y constantes compartidas por todo el proyecto."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"

SEASON = 2025

# Compuestos de seco (las carreras con INTERMEDIATE/WET quedan fuera del MVP)
DRY_COMPOUNDS = ["SOFT", "MEDIUM", "HARD"]
WET_COMPOUNDS = ["INTERMEDIATE", "WET"]

COMPOUND_COLORS = {
    "SOFT": "#DA291C",
    "MEDIUM": "#FFD12E",
    "HARD": "#F0F0EC",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
}

# Abreviaturas de Gran Premio (columnas del mapa de calor)
GP_ABBR = {
    "Australian Grand Prix": "AUS", "Chinese Grand Prix": "CHN", "Japanese Grand Prix": "JPN",
    "Bahrain Grand Prix": "BHR", "Saudi Arabian Grand Prix": "KSA", "Miami Grand Prix": "MIA",
    "Emilia Romagna Grand Prix": "EMI", "Monaco Grand Prix": "MON", "Spanish Grand Prix": "ESP",
    "Canadian Grand Prix": "CAN", "Austrian Grand Prix": "AUT", "British Grand Prix": "GBR",
    "Belgian Grand Prix": "BEL", "Hungarian Grand Prix": "HUN", "Dutch Grand Prix": "NED",
    "Italian Grand Prix": "ITA", "Azerbaijan Grand Prix": "AZE", "Singapore Grand Prix": "SGP",
    "United States Grand Prix": "USA", "Mexico City Grand Prix": "MEX", "São Paulo Grand Prix": "BRA",
    "Las Vegas Grand Prix": "LVG", "Qatar Grand Prix": "QAT", "Abu Dhabi Grand Prix": "ABU",
}

# Nombres en español para textos
GP_ES = {
    "Australian Grand Prix": "GP de Australia", "Chinese Grand Prix": "GP de China",
    "Japanese Grand Prix": "GP de Japón", "Bahrain Grand Prix": "GP de Baréin",
    "Saudi Arabian Grand Prix": "GP de Arabia Saudí", "Miami Grand Prix": "GP de Miami",
    "Emilia Romagna Grand Prix": "GP de Emilia-Romaña", "Monaco Grand Prix": "GP de Mónaco",
    "Spanish Grand Prix": "GP de España", "Canadian Grand Prix": "GP de Canadá",
    "Austrian Grand Prix": "GP de Austria", "British Grand Prix": "GP de Gran Bretaña",
    "Belgian Grand Prix": "GP de Bélgica", "Hungarian Grand Prix": "GP de Hungría",
    "Dutch Grand Prix": "GP de Países Bajos", "Italian Grand Prix": "GP de Italia",
    "Azerbaijan Grand Prix": "GP de Azerbaiyán", "Singapore Grand Prix": "GP de Singapur",
    "United States Grand Prix": "GP de Estados Unidos", "Mexico City Grand Prix": "GP de México",
    "São Paulo Grand Prix": "GP de São Paulo", "Las Vegas Grand Prix": "GP de Las Vegas",
    "Qatar Grand Prix": "GP de Qatar", "Abu Dhabi Grand Prix": "GP de Abu Dabi",
}
