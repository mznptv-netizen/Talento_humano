"""Catálogos de selección colombianos, incluidos para uso sin conexión."""
import json
import sys
from pathlib import Path
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
CATALOGOS = json.loads((ROOT / 'catalogos_colombia.json').read_text(encoding='utf-8'))
MUNICIPIOS = CATALOGOS['municipios']
LISTAS = {key: ['', *CATALOGOS[key]] for key in ('eps', 'afp', 'cesantias', 'entidad_financiera')}

BANK_CODES = CATALOGOS['codigos_banco']

def bank_code(name):
    from relaciones import fold
    value = fold(name).strip()
    aliases = {'banco davivienda': 'Davivienda', 'bbva': 'BBVA Colombia', 'scotiabank colpatria': 'Davibank', 'bancolombia s.a.': 'Bancolombia'}
    value = fold(aliases.get(value, name)).strip()
    return next((code for bank, code in BANK_CODES.items() if fold(bank) == value), '')
