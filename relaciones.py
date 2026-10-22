"""Reglas de asignaciones: una fila = regional + sede + modalidad + perfil + horas."""
from decimal import Decimal
import re
import unicodedata

REGIONS = ('Bogotá', 'Cundinamarca')
REGIONAL_OPTIONS = (*REGIONS, 'Ambas')
SEDES = ('Femenino', 'Redentor', 'Cipla', 'Cetra', 'Cajica')
MODALIDADES = {
    'Bogotá': ('CAE MASCULINO REDENTOR', 'CAE 27', 'CIP 10', 'INTERNADO RAJ FEMENINO',
               'CIP MASCULINO', 'CETRA', 'INTERNADO RAJ MASCULINO'),
    'Cundinamarca': ('CAE FEMENINO', 'CIP MASCULINO/FEM', 'CAE MASCULINO REDENTOR',
                    'INTERNADO RAJ MASCULINO'),
}
PERIODOS = ('Semanales', 'Mensuales')
ASSIGNMENT_KEYS = ('regional', 'sede', 'modalidad', 'perfil', 'horas')


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', str(text).casefold()) if unicodedata.category(c) != 'Mn')


def alphabetic(text):
    # Español: la ñ se ordena después de n; las tildes no cambian la letra base.
    return fold(str(text).casefold().replace('ñ', 'n~'))


def members(regional):
    return REGIONS if regional == 'Ambas' else ((regional,) if regional in REGIONS else ())


def modalities(regional):
    return tuple(dict.fromkeys(value for r in members(regional) for value in MODALIDADES[r]))


def hundredths(value, label='Horas'):
    text = str(value).strip().replace(',', '.')
    if not re.fullmatch(r'\d{1,6}(?:\.\d{1,2})?', text):
        raise ValueError(f'{label}: usa un número positivo con máximo dos decimales, por ejemplo 20 o 20,5.')
    number = int(Decimal(text) * 100)
    if number <= 0:
        raise ValueError(f'{label} debe ser mayor que cero.')
    return number


def hours_text(number):
    return format(Decimal(number) / 100, 'f').rstrip('0').rstrip('.') if number % 100 else str(number // 100)


def canonical_assignments(rows, regional, total, period):
    if not rows:
        if str(total).strip():
            raise ValueError('Distribuye las horas totales en al menos una asignación.')
        return []  # Importaciones antiguas permanecen visibles como pendientes.
    if period not in PERIODOS:
        raise ValueError('Elige si las horas son semanales o mensuales.')
    total_units = hundredths(total, 'Horas totales')
    allowed_regions = members(regional)
    result, seen = [], set()
    for i, raw in enumerate(rows, 1):
        item = {key: str(raw.get(key, '')).strip() for key in ASSIGNMENT_KEYS}
        if item['regional'] not in allowed_regions:
            raise ValueError(f'Asignación {i}: regional incompatible con {regional}.')
        if item['sede'] not in SEDES:
            raise ValueError(f'Asignación {i}: selecciona una sede válida.')
        if item['modalidad'] not in MODALIDADES[item['regional']]:
            raise ValueError(f'Asignación {i}: modalidad incompatible con su regional.')
        if not item['perfil'] or len(item['perfil']) > 120:
            raise ValueError(f'Asignación {i}: escribe un perfil de 1 a 120 caracteres.')
        identity = tuple(fold(item[key]) for key in ASSIGNMENT_KEYS[:-1])
        if identity in seen:
            raise ValueError(f'Asignación {i}: combinación repetida; reúne sus horas en una sola fila.')
        seen.add(identity)
        item['horas'] = hours_text(hundredths(item['horas'], f'Horas de la asignación {i}'))
        result.append(item)
    if {r['regional'] for r in result} != set(allowed_regions):
        raise ValueError('Si eliges Ambas, registra al menos una asignación en cada regional.')
    distributed = sum(hundredths(r['horas']) for r in result)
    if distributed != total_units:
        raise ValueError(f'Las horas distribuidas ({hours_text(distributed)}) deben coincidir con el total ({hours_text(total_units)}).')
    return sorted(result, key=lambda row: tuple(alphabetic(row[k]) for k in ASSIGNMENT_KEYS[:-1]))


def summary(rows, key):
    return '; '.join(sorted({r[key] for r in rows}, key=alphabetic))
