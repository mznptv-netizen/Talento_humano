"""Talento Humano IPSICOL — Python 3, Tkinter, SQLite; openpyxl para importar Excel."""
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
import os
import re
import sqlite3
import sys
if __name__ == '__main__':
    sys.modules['talento_humano'] = sys.modules[__name__]
import unicodedata
from relaciones import REGIONS, REGIONAL_OPTIONS, SEDES, MODALIDADES, PERIODOS, members, canonical_assignments, summary, hundredths, hours_text, alphabetic
from catalogos import bank_code
from contextlib import nullcontext, closing
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

FIELDS = [
    ('regional', 'Regional', 'Asignaciones'),
    ('numero', 'Número de empleado (No)', 'Laboral'),
    ('documento', 'Documento', 'Personal'),
    ('apellidos', 'Apellidos', 'Personal'),
    ('nombres', 'Nombres', 'Personal'),
    ('nombre', 'Apellidos y nombres', 'Personal'),
    ('sede', 'Sedes', 'Asignaciones'),
    ('modalidad', 'Modalidades', 'Asignaciones'),
    ('horas_totales', 'Horas totales asignadas', 'Asignaciones'),
    ('periodo_horas', 'Periodo de las horas', 'Asignaciones'),
    ('fecha_ingreso', 'Fecha de ingreso', 'Laboral'),
    ('fecha_fin', 'Fecha de finalización del contrato', 'Laboral'),
    ('cargo', 'Cargo', 'Laboral'),
    ('direccion', 'Dirección', 'Contacto'),
    ('barrio', 'Barrio', 'Contacto'),
    ('ciudad', 'Ciudad', 'Contacto'),
    ('fijo', 'Teléfono fijo', 'Contacto'),
    ('celular', 'Número de celular', 'Contacto'),
    ('correo', 'Correo electrónico', 'Contacto'),
    ('eps', 'EPS', 'Afiliaciones'),
    ('afp', 'Fondo de pensiones (AFP)', 'Afiliaciones'),
    ('cesantias', 'Cesantías', 'Afiliaciones'),
    ('riesgo', 'Clase de riesgo', 'Afiliaciones'),
    ('salario', 'Salario (COP)', 'Bancarios'),
    ('fecha_nacimiento', 'Fecha de nacimiento', 'Personal'),
    ('lugar_nacimiento', 'Lugar de nacimiento', 'Personal'),
    ('fecha_expedicion', 'Fecha de expedición del documento', 'Personal'),
    ('lugar_expedicion', 'Lugar de expedición', 'Personal'),
    ('rh', 'Grupo sanguíneo y RH', 'Personal'),
    ('sexo', 'Sexo (F / M)', 'Personal'),
    ('estatura', 'Estatura (cm)', 'Personal'),
    ('entidad_financiera', 'Entidad financiera', 'Bancarios'),
    ('codigo_banco', 'Código del banco', 'Bancarios'),
    ('cuenta', 'N.º de cuenta', 'Bancarios'),
    ('tipo_cuenta', 'Tipo de cuenta (T. CUENTA)', 'Bancarios'),
    ('datos_actualizados', 'Datos actualizados', 'Laboral'),
    ('fecha_contrato', 'Fecha contrato', 'Laboral'),
    ('prorroga1', 'Prórroga 1', 'Laboral'),
    ('tipo_contrato', 'Tipo de contrato', 'Laboral'),
]
KEYS = [f[0] for f in FIELDS]
LABELS = {k: label for k, label, _ in FIELDS}
DATES = ('fecha_ingreso', 'fecha_fin', 'fecha_nacimiento', 'fecha_expedicion', 'fecha_contrato', 'prorroga1')
REQUIRED = ('regional', 'documento', 'nombre')
CHOICES = {'rh': ('', 'O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'),
           'sexo': ('', 'F', 'M'), 'riesgo': ('', '1', '2', '3', '4', '5'),
           'tipo_contrato': ('', 'Definido', 'Indefinido'),
           'tipo_cuenta': ('', 'Ahorros', 'Corriente'),
           'periodo_horas': ('', *PERIODOS),
           'regional': ('', *REGIONAL_OPTIONS)}


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value).casefold())
                   if unicodedata.category(c) != 'Mn')


class ValidationError(ValueError):
    def __init__(self, key, message):
        super().__init__(message)
        self.key = key


def validate(values):
    """Convierte datos del formulario; conserva identificadores como texto."""
    data = {key: str(values.get(key, '')).strip() for key in KEYS}
    data['riesgo'] = {'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5'}.get(data['riesgo'].upper(), data['riesgo'])
    data['tipo_contrato'] = {'termino fijo': 'Definido', 'definido': 'Definido', 'termino indefinido': 'Indefinido', 'indefinido': 'Indefinido'}.get(normalize(data['tipo_contrato']), data['tipo_contrato'])
    if data['apellidos'] or data['nombres']:
        if not data['apellidos'] or not data['nombres']:
            raise ValidationError('apellidos', 'Completa Apellidos y Nombres en campos separados.')
        data['apellidos'] = ' '.join(data['apellidos'].split())
        data['nombres'] = ' '.join(data['nombres'].split())
        data['nombre'] = data['apellidos'] + ' ' + data['nombres']
    if not data['codigo_banco']:
        data['codigo_banco'] = bank_code(data['entidad_financiera'])
    if data['horas_totales']:
        try:
            data['horas_totales'] = hours_text(hundredths(data['horas_totales'], 'Horas totales'))
        except ValueError as error:
            raise ValidationError('horas_totales', str(error)) from error
    for key in REQUIRED:
        if not data[key]:
            raise ValidationError(key, f'Completa el campo {LABELS[key]}.')
    for key in KEYS:
        if len(data[key]) > 500:
            raise ValidationError(key, f'{LABELS[key]}: máximo 500 caracteres.')
    for key in DATES:
        if data[key]:
            try:
                if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', data[key]):
                    raise ValueError()
                data[key] = datetime.strptime(data[key], '%d/%m/%Y').date().isoformat()
            except ValueError:
                raise ValidationError(key, f'{LABELS[key]}: usa una fecha válida DD/MM/AAAA.')
    if data['fecha_ingreso'] and data['fecha_fin'] and data['fecha_fin'] < data['fecha_ingreso']:
        raise ValidationError('fecha_fin', 'La finalización no puede ser anterior al ingreso.')
    for key in ('fecha_nacimiento', 'fecha_expedicion'):
        if data[key] and data[key] > date.today().isoformat():
            raise ValidationError(key, f'{LABELS[key]} no puede ser una fecha futura.')
    birth = data['fecha_nacimiento']
    for key in ('fecha_ingreso', 'fecha_expedicion'):
        if birth and data[key] and data[key] < birth:
            raise ValidationError(key, f'{LABELS[key]} no puede ser anterior al nacimiento.')
    if data['correo'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', data['correo']):
        raise ValidationError('correo', 'Revisa el correo electrónico: ejemplo@empresa.com.')
    for key, options in CHOICES.items():
        if data[key] not in options:
            raise ValidationError(key, f'Selecciona un valor válido para {LABELS[key]}.')
    for key, decimal_places in [('salario', 2), ('estatura', 1)]:
        if not data[key]:
            continue
        if not re.fullmatch(r'\d+(?:[.,]\d{1,' + str(decimal_places) + r'})?', data[key]):
            raise ValidationError(key, f'{LABELS[key]}: escribe un número sin separadores de miles.')
        value = Decimal(data[key].replace(',', '.'))
        if key == 'estatura' and not Decimal('30') <= value <= Decimal('300'):
            raise ValidationError(key, 'Escribe la estatura en centímetros, por ejemplo: 170.')
        data[key] = format(value, 'f')
    return data


def display(key, value):
    if key in DATES and value:
        try:
            return date.fromisoformat(value).strftime('%d/%m/%Y')
        except ValueError:
            return value  # Conserva fechas históricas pendientes de revisión.
    if key == 'salario' and value:
        number = Decimal(value)
        digits = 0 if number == number.to_integral_value() else 2
        return format(number, f',.{digits}f').translate(str.maketrans({',': '.', '.': ','}))
    return value


class Database:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.create_function('fold', 1, normalize)
        self.conn.create_function('sort_es', 1, alphabetic)
        try:
            self._migrate()
        except Exception:
            self.conn.close()
            raise

    def _migrate(self):
        if self.conn.execute('PRAGMA user_version').fetchone()[0] > 2:
            raise ValueError('La base fue creada por una versión más reciente del programa.')
        columns = ', '.join(f"{key} TEXT NOT NULL DEFAULT ''" for key in KEYS)
        self.conn.execute(f"""CREATE TABLE IF NOT EXISTS empleados (
            id INTEGER PRIMARY KEY, {columns}, nombre_original TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL, actualizado TEXT NOT NULL,
            UNIQUE(numero), UNIQUE(documento))""")
        existing = {row[1] for row in self.conn.execute('PRAGMA table_info(empleados)')}
        needs_conversion = self.conn.execute("SELECT 1 FROM empleados WHERE upper(riesgo) IN ('I','II','III','IV','V') LIMIT 1").fetchone() if 'riesgo' in existing else False
        old_contract_or_date = self.conn.execute("SELECT 1 FROM empleados WHERE fold(tipo_contrato) IN ('termino fijo','termino indefinido') OR prorroga1 LIKE '__/__/____' LIMIT 1").fetchone() if {'tipo_contrato','prorroga1'} <= existing else False
        if set(KEYS + ['nombre_original']) - existing or needs_conversion or old_contract_or_date:
            self.backup(self.path.with_name(self.path.stem + '_antes_actualizacion_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db'))
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            for key in KEYS + ['nombre_original']:
                if key not in existing:
                    self.conn.execute(f"ALTER TABLE empleados ADD COLUMN {key} TEXT NOT NULL DEFAULT ''")
            self.conn.execute("UPDATE empleados SET nombre_original=nombre WHERE nombre_original=''")
            for old, new in zip(('I','II','III','IV','V'), ('1','2','3','4','5')):
                self.conn.execute('UPDATE empleados SET riesgo=?, version=version+1 WHERE upper(riesgo)=?', (new,old))
            self.conn.execute("UPDATE empleados SET tipo_contrato='Definido', version=version+1 WHERE fold(tipo_contrato)='termino fijo'")
            self.conn.execute("UPDATE empleados SET tipo_contrato='Indefinido', version=version+1 WHERE fold(tipo_contrato)='termino indefinido'")
            for row in self.conn.execute("SELECT id, prorroga1 FROM empleados WHERE prorroga1<>''").fetchall():
                try:
                    converted = datetime.strptime(row['prorroga1'], '%d/%m/%Y').date().isoformat()
                except ValueError:
                    continue
                self.conn.execute('UPDATE empleados SET prorroga1=?, version=version+1 WHERE id=?', (converted,row['id']))
            self.conn.execute("""CREATE TABLE IF NOT EXISTS empleado_regionales (
                empleado_id INTEGER NOT NULL REFERENCES empleados(id) ON DELETE CASCADE,
                regional TEXT NOT NULL CHECK(regional IN ('Bogotá','Cundinamarca')),
                PRIMARY KEY(empleado_id,regional))""")
            self.conn.execute("""CREATE TABLE IF NOT EXISTS asignaciones (
                id INTEGER PRIMARY KEY, empleado_id INTEGER NOT NULL,
                regional TEXT NOT NULL, sede TEXT NOT NULL, modalidad TEXT NOT NULL,
                perfil TEXT NOT NULL, horas_centesimas INTEGER NOT NULL CHECK(horas_centesimas>0),
                FOREIGN KEY(empleado_id,regional) REFERENCES empleado_regionales(empleado_id,regional),
                UNIQUE(empleado_id,regional,sede,modalidad,perfil))""")
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_asignaciones_empleado ON asignaciones(empleado_id)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_asignaciones_filtro ON asignaciones(regional,sede,modalidad)')
            for row in self.conn.execute('SELECT id,regional FROM empleados').fetchall():
                for region in members(row['regional']):
                    self.conn.execute('INSERT OR IGNORE INTO empleado_regionales VALUES (?,?)', (row['id'],region))
            self.conn.execute('PRAGMA user_version=2')

    def next_number(self, reserved=()):
        values = [r[0] for r in self.conn.execute('SELECT numero FROM empleados')] + list(reserved)
        return str(max((int(v) for v in values if str(v).isascii() and str(v).isdigit()), default=0) + 1)

    def assignments(self, employee_id):
        rows = self.conn.execute('SELECT regional,sede,modalidad,perfil,horas_centesimas FROM asignaciones WHERE empleado_id=? ORDER BY sort_es(regional),sort_es(sede),sort_es(modalidad),sort_es(perfil)', (employee_id,))
        return [dict(regional=r['regional'],sede=r['sede'],modalidad=r['modalidad'],perfil=r['perfil'],horas=hours_text(r['horas_centesimas'])) for r in rows]

    def prepare(self, raw, assignments):
        data = validate(raw)
        try:
            assignments = canonical_assignments(assignments, data['regional'], data['horas_totales'], data['periodo_horas'])
        except ValueError as error:
            raise ValidationError('asignaciones', str(error)) from error
        if assignments:
            data['sede'] = summary(assignments, 'sede')
            data['modalidad'] = summary(assignments, 'modalidad')
        return data, assignments

    def save(self, raw, employee_id=None, version=None, transaction=True, assignments=None):
        now = datetime.now().isoformat(timespec='seconds')
        try:
            with self.conn if transaction else nullcontext():
                if not self.conn.in_transaction:
                    self.conn.execute('BEGIN IMMEDIATE')
                if assignments is None:
                    assignments = raw.get('_asignaciones', self.assignments(employee_id) if employee_id is not None else [])
                data, assignments = self.prepare(raw, assignments)
                if not data['numero']:
                    previous = self.get(employee_id) if employee_id is not None else None
                    data['numero'] = previous['numero'] if previous else self.next_number()
                if employee_id is None:
                    sql = f"INSERT INTO empleados ({', '.join(KEYS)}, nombre_original, creado, actualizado) VALUES ({', '.join('?' for _ in range(len(KEYS)+3))})"
                    result = self.conn.execute(sql, [data[k] for k in KEYS] + [str(raw.get('nombre') or data['nombre']),now,now])
                    employee_id = result.lastrowid
                else:
                    sql = f"UPDATE empleados SET {', '.join(k+'=?' for k in KEYS)}, actualizado=?, version=version+1 WHERE id=? AND version=?"
                    result = self.conn.execute(sql, [data[k] for k in KEYS] + [now,employee_id,version])
                    if result.rowcount != 1:
                        raise ValueError('El registro cambió en otra ventana. Vuelve a abrirlo antes de editar.')
                self.conn.execute('DELETE FROM asignaciones WHERE empleado_id=?', (employee_id,))
                self.conn.execute('DELETE FROM empleado_regionales WHERE empleado_id=?', (employee_id,))
                self.conn.executemany('INSERT INTO empleado_regionales VALUES (?,?)', [(employee_id,r) for r in members(data['regional'])])
                self.conn.executemany('INSERT INTO asignaciones (empleado_id,regional,sede,modalidad,perfil,horas_centesimas) VALUES (?,?,?,?,?,?)',
                    [(employee_id,r['regional'],r['sede'],r['modalidad'],r['perfil'],hundredths(r['horas'])) for r in assignments])
                return employee_id
        except sqlite3.IntegrityError as error:
            raise ValueError('Ya existe ese número/documento o una asignación incompatible. No se guardaron cambios.') from error

    def get(self, employee_id):
        return self.conn.execute('SELECT * FROM empleados WHERE id=?', (employee_id,)).fetchone()

    def search(self, query='', regional=None, sede=None, modalidad=None, perfil=None,
               documento='', tipo_contrato='', pendientes=''):
        combined = " || ' ' || ".join('e.' + k for k in KEYS)
        combined += " || ' ' || COALESCE((SELECT group_concat(a.perfil,' ') FROM asignaciones a WHERE a.empleado_id=e.id),'')"
        conditions, params = [], []
        for token in query.strip().split():
            conditions.append(f'instr(fold({combined}),fold(?))>0');params.append(token)
        if regional in REGIONS:
            conditions.append('EXISTS (SELECT 1 FROM empleado_regionales er WHERE er.empleado_id=e.id AND er.regional=?)');params.append(regional)
        elif regional == 'Ambas':
            conditions.append("e.regional='Ambas'")
        elif regional == '':
            conditions.append('NOT EXISTS (SELECT 1 FROM empleado_regionales er WHERE er.empleado_id=e.id)')
        elif regional is not None:
            raise ValueError('Filtro regional no válido.')
        filters, assignment_params = [], []
        for key, value in (('sede',sede),('modalidad',modalidad)):
            if value:
                filters.append(f'a.{key}=?');assignment_params.append(value)
        if perfil:
            filters.append('instr(fold(a.perfil),fold(?))>0');assignment_params.append(perfil.strip())
        if filters:
            if regional in REGIONS:
                filters.append('a.regional=?');assignment_params.append(regional)
            clause = 'EXISTS (SELECT 1 FROM asignaciones a WHERE a.empleado_id=e.id AND ' + ' AND '.join(filters) + ')'
            if sede and not modalidad and not perfil:
                clause = '(' + clause + " OR (NOT EXISTS (SELECT 1 FROM asignaciones a WHERE a.empleado_id=e.id) AND fold(e.sede)=fold(?)))"
                assignment_params.append(sede)
            conditions.append(clause);params.extend(assignment_params)
        if documento:
            conditions.append('instr(e.documento,?)>0');params.append(documento.strip())
        if tipo_contrato:
            conditions.append('e.tipo_contrato=?');params.append(tipo_contrato)
        if pendientes == 'Nombres por revisar':
            conditions.append("(e.apellidos='' OR e.nombres='')")
        elif pendientes == 'Sin distribución de horas':
            conditions.append('NOT EXISTS (SELECT 1 FROM asignaciones a WHERE a.empleado_id=e.id)')
        return self.conn.execute('SELECT e.* FROM empleados e WHERE ' + (' AND '.join(conditions) or '1') +
                                 ' ORDER BY sort_es(e.nombre),e.id', params).fetchall()

    def region_counts(self):
        return {r:len(self.search(regional=r)) for r in (*REGIONS,'')}

    def import_rows(self, rows):
        added, skipped = 0,0
        rows = list(rows)
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            reserved = [str(raw.get('numero','')).strip() for _,raw in rows]
            for excel_row, raw in rows:
                raw = dict(raw)
                try:
                    if not str(raw.get('numero','')).strip():
                        old = self.conn.execute('SELECT numero FROM empleados WHERE documento=?',(str(raw.get('documento','')).strip(),)).fetchone()
                        raw['numero'] = old['numero'] if old else self.next_number(reserved)
                        reserved.append(raw['numero'])
                    data, assignments = self.prepare(raw, raw.get('_asignaciones',[]))
                    matches = self.conn.execute('SELECT * FROM empleados WHERE numero=? OR documento=?',(data['numero'],data['documento'])).fetchall()
                    if matches:
                        if len(matches)==1 and all(matches[0][k]==data[k] for k in KEYS) and self.assignments(matches[0]['id'])==assignments:
                            skipped += 1;continue
                        raise ValueError('Número o documento ya registrado con datos diferentes. No se sobrescribe.')
                    self.save(raw, transaction=False, assignments=assignments)
                    added += 1
                except (ValueError,sqlite3.Error) as error:
                    raise ValueError(f'Fila {excel_row}: {error}') from error
        return added,skipped

    def backup(self, path):
        target = Path(path).resolve()
        if target == self.path:
            raise ValueError('Selecciona un archivo distinto de la base de datos en uso.')
        with closing(sqlite3.connect(target)) as copy:
            self.conn.backup(copy)

    def close(self):
        self.conn.close()


def default_path():
    if os.name == 'nt':
        root = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local')))
    else:
        root = Path.home() / '.local' / 'share'
    return root / 'IPSICOL' / 'TalentoHumano' / 'talento_humano.db'


def main():
    if '--smoke-test' in sys.argv:
        return smoke_test()
    try:
        db = Database(default_path())
    except (OSError, sqlite3.Error) as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('No se pudo abrir la base de datos', str(error), parent=root)
        root.destroy()
        return 1
    from interfaz import App
    App(db).mainloop()
    return 0


def smoke_test():
    """Comprueba el ejecutable congelado con una base temporal, sin datos reales."""
    import tempfile
    import traceback
    report = Path(os.environ.get('IPSICOL_SMOKE_REPORT', str(Path(tempfile.gettempdir()) / 'ipsicol-smoke.txt')))
    try:
        import openpyxl
        from importar_excel import ImportDialog
        from interfaz import App, EmployeeEditor, EmployeeDetails, AdvancedSearch
        # Se cierra la conexión antes de eliminar la carpeta, incluso si falla Tk.
        with tempfile.TemporaryDirectory() as folder, closing(Database(Path(folder) / 'prueba.db')) as db:
            app = None
            try:
                db.save({'regional': 'Bogotá', 'numero': '1', 'documento': 'PRUEBA', 'nombre': 'Prueba de inicio'})
                app = App(db)
                assert app.active_region is None
                assert len(app.tree.get_children()) == 1
                app.set_region('Bogotá')
                app.withdraw()
                app.update_idletasks()
                if not hasattr(app, 'logo'):
                    raise RuntimeError('No se pudo cargar el logo incluido en el ejecutable.')
                details = EmployeeDetails(app, db.get(1))
                details.update_idletasks()
                if set(details.field_widgets) != set(KEYS):
                    raise RuntimeError('Faltan campos en la ficha completa.')
                details.destroy()
                if set(app.tree['columns']) != set(KEYS):
                    raise RuntimeError('Faltan columnas en la tabla completa.')
                editor = EmployeeEditor(app, db.get(1))
                editor.update_idletasks()
                if set(editor.widgets) != set(KEYS):
                    raise RuntimeError('Faltan campos en el formulario.')
                for key in DATES:
                    if not hasattr(editor.widgets[key], 'open'):
                        raise RuntimeError('Falta calendario: ' + key)
                calendar_window = editor.widgets['prorroga1'].open()
                calendar_window.year.set('2028')
                calendar_window.month.set('Febrero')
                calendar_window.draw()
                calendar_window.choose(date(2028, 2, 29))
                assert editor.vars['prorroga1'].get() == '29/02/2028'
                cities = editor.widgets['ciudad'].open()
                cities.query.set('cajica')
                cities.update_idletasks()
                choices = cities.tree.get_children()
                assert choices, 'No se cargó el catálogo colombiano.'
                cities.tree.selection_set(choices[0])
                cities.choose()
                assert editor.vars['ciudad'].get() == 'Cajicá (Cundinamarca)'
                assert editor.widgets['numero'].cget('state') == 'readonly'
                assert editor.widgets['tipo_contrato'].cget('values') == ['', 'Definido', 'Indefinido']
                editor.destroy()
                importer = ImportDialog(app)
                importer.update_idletasks()
                importer.close()
                from unittest.mock import patch
                def fail_dialog(*args, **kwargs):
                    raise RuntimeError('La interfaz rechazó datos válidos: ' + str(args))
                with patch('tkinter.messagebox.showwarning', fail_dialog), patch('tkinter.messagebox.showerror', fail_dialog):
                    new = EmployeeEditor(app)
                    for key,value in {'apellidos':'Godoy Ejemplo','nombres':'Nicolas','documento':'UI-99',
                                      'regional':'Ambas','horas_totales':'40','periodo_horas':'Semanales','salario':'1800000'}.items():
                        new.vars[key].set(value)
                    panel = new.assignment_panel
                    panel.region_changed('Ambas')
                    assert len(panel.controls['modalidad'].cget('values')) == 10
                    data = [('Bogotá','Redentor','CAE MASCULINO REDENTOR','Gestor','12'),
                            ('Bogotá','Redentor','CAE MASCULINO REDENTOR','Psicólogo','8'),
                            ('Cundinamarca','Cajica','CAE FEMENINO','Gestor','20')]
                    for row in data:
                        panel.inputs['regional'].set(row[0]);panel.assignment_region_changed(row[0])
                        for key,value in zip(('regional','sede','modalidad','perfil','horas'),row):
                            panel.inputs[key].set(value)
                        panel.add()
                    new.vars['entidad_financiera'].set('Bancolombia');new.bank_selected('Bancolombia')
                    assert new.vars['codigo_banco'].get() == '1007'
                    new.save()
                    assert app.active_region is None and len(app.tree.get_children()) == 2
                    row = db.search('UI-99')[0]
                    assert row['nombre'] == 'Godoy Ejemplo Nicolas'
                    assert len(db.assignments(row['id'])) == 3
                    app.set_region('Cundinamarca')
                    assert len(app.tree.get_children()) == 1
                    advanced = AdvancedSearch(app)
                    advanced.vars['sede'].set('Redentor');advanced.apply()
                    assert len(app.tree.get_children()) == 0
                    app.show_home()
                    assert len(app.tree.get_children()) == 2
                    edit = EmployeeEditor(app, db.get(row['id']))
                    assert edit.vars['salario'].get() == '1800000'
                    edit.vars['cargo'].set('Coordinación de prueba');edit.save()
                    assert len(db.assignments(row['id'])) == 3
                if len(db.search(documento='PRUEBA')) != 1:
                    raise RuntimeError('Fallo la consulta de datos de prueba.')
            finally:
                if app is not None:
                    app.destroy()
        report.write_text('OK', encoding='utf-8')
        return 0
    except Exception:
        report.write_text(traceback.format_exc(), encoding='utf-8')
        return 1


if __name__ == '__main__':
    sys.exit(main())
