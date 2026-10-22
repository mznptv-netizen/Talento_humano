"""Pruebas aisladas: python pruebas.py."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import Mock, patch
from pathlib import Path
from talento_humano import Database, FIELDS, validate, ValidationError, display


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / 'test.db')
        self.raw = {'regional': 'Bogotá', 'numero': '0007', 'documento': '0012345', 'nombre': 'María Prueba',
                    'sede': 'Cajicá', 'fecha_ingreso': '01/02/2026', 'fecha_fin': '01/02/2027',
                    'cargo': 'Auxiliar', 'direccion': 'Calle de prueba', 'barrio': 'Centro',
                    'ciudad': 'Bogotá', 'fijo': '00123', 'celular': '00300123',
                    'correo': 'prueba@example.com', 'eps': 'EPS ejemplo', 'afp': 'AFP ejemplo',
                    'cesantias': 'Fondo ejemplo', 'riesgo': '2', 'salario': '1500000,50',
                    'fecha_nacimiento': '29/02/2000', 'lugar_nacimiento': 'Bogotá',
                    'fecha_expedicion': '01/03/2018', 'lugar_expedicion': 'Bogotá',
                    'rh': 'O+', 'sexo': 'F', 'estatura': '170,5',
                    'entidad_financiera': 'Banco prueba', 'codigo_banco': '001',
                    'cuenta': '000123456789', 'tipo_cuenta': 'Ahorros',
                    'datos_actualizados': 'Sí', 'fecha_contrato': '01/02/2026',
                    'prorroga1': '01/02/2027', 'tipo_contrato': 'Definido'}

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_round_trip_all_39_fields_and_restart(self):
        self.assertEqual(len(FIELDS), 39)
        employee_id = self.db.save(self.raw)
        path = self.db.path
        self.db.close()
        self.db = Database(path)
        row = self.db.get(employee_id)
        for key, expected in validate(self.raw).items():
            self.assertEqual(row[key], expected)
        self.assertEqual(row['cuenta'], '000123456789')
        self.assertEqual(display('fecha_nacimiento', row['fecha_nacimiento']), '29/02/2000')

    def test_edit_and_concurrent_edit_protection(self):
        employee_id = self.db.save(self.raw)
        self.db.save(dict(self.raw, cargo='Coordinación'), employee_id, 1)
        with self.assertRaises(ValueError):
            self.db.save(dict(self.raw, cargo='Cambio obsoleto'), employee_id, 1)
        self.assertEqual(self.db.get(employee_id)['cargo'], 'Coordinación')

    def test_unique_identifiers(self):
        self.db.save(self.raw)
        for changes in ({'numero': '8'}, {'documento': '999'}):
            with self.assertRaises(ValueError):
                self.db.save(dict(self.raw, **changes))
        self.assertEqual(len(self.db.search()), 1)

    def test_search_accent_case_and_sql_characters(self):
        self.db.save(self.raw)
        for query in ('MARIA', 'cajica', '0007', '0012345', 'Auxiliar', 'definido'):
            self.assertEqual(len(self.db.search(query)), 1)
        for query in ('%', '_', "' OR 1=1 --"):
            self.assertEqual(len(self.db.search(query)), 0)

    def test_backup_restore_and_source_protection(self):
        self.db.save(self.raw)
        path = Path(self.temp.name) / 'backup.db'
        self.db.backup(path)
        with closing(sqlite3.connect(path)) as restored:
            self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(restored.execute('SELECT cuenta FROM empleados').fetchone()[0], '000123456789')
        with self.assertRaises(sqlite3.ProgrammingError):
            restored.execute('SELECT 1')
        path.unlink()
        self.assertFalse(path.exists())
        with self.assertRaises(ValueError):
            self.db.backup(self.db.path)

    def test_backup_closes_destination_even_on_error(self):
        # Conserva referencias: detecta fugas también en Linux, sin depender del GC.
        original_connect = sqlite3.connect
        connections = []
        def tracked_connect(*args, **kwargs):
            connection = original_connect(*args, **kwargs)
            connections.append(connection)
            return connection
        with patch('talento_humano.sqlite3.connect', side_effect=tracked_connect):
            self.db.backup(Path(self.temp.name) / 'success.db')
            failed_source = Mock()
            failed_source.backup.side_effect = sqlite3.OperationalError('Fallo de copia simulado')
            with patch.object(self.db, 'conn', failed_source):
                with self.assertRaises(sqlite3.OperationalError):
                    self.db.backup(Path(self.temp.name) / 'failure.db')
        try:
            self.assertEqual(len(connections), 2)
            for connection in connections:
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute('SELECT 1')
        finally:
            for connection in connections:
                connection.close()

    def test_invalid_inputs_and_optional_empty_values(self):
        invalid = [('prorroga1', '31/02/2026'), ('riesgo', '6'), ('tipo_contrato', 'Obra o labor'), ('documento', ''), ('nombre', ' '),
                   ('fecha_nacimiento', '31/02/2000'), ('fecha_fin', '01/01/2026'),
                   ('fecha_ingreso', '2026-02-01'), ('fecha_expedicion', '01/01/1999'),
                   ('correo', 'sin-arroba'), ('salario', '-5'), ('salario', '1.500.000'),
                   ('salario', 'NaN'), ('estatura', '1,70'), ('sexo', 'X')]
        for key, value in invalid:
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                self.db.save(dict(self.raw, **{key: value}))
        self.assertEqual(len(self.db.search()), 0)
        self.db.save({'regional': 'Bogotá', 'numero': '1', 'documento': '2', 'nombre': 'Registro mínimo'})
        self.assertEqual(len(self.db.search()), 1)

    def test_import_atomicity_and_exact_duplicates(self):
        self.db.save(self.raw)
        new = dict(self.raw, numero='0008', documento='00999', nombre='Segundo')
        self.assertEqual(self.db.import_rows([(2, self.raw), (3, new)]), (1, 1))
        third = dict(self.raw, numero='0009', documento='00888')
        conflict = dict(self.raw, cargo='Cargo cambiado')
        with self.assertRaisesRegex(ValueError, 'Fila 5'):
            self.db.import_rows([(4, third), (5, conflict)])
        self.assertEqual(len(self.db.search()), 2)
        self.assertEqual(len(self.db.search('00888')), 0)
        with self.assertRaisesRegex(ValueError, 'Fila 6'):
            self.db.import_rows([(6, dict(self.raw, numero='100', documento='00999'))])

    def test_regional_separation_and_required_region(self):
        self.db.save(self.raw)
        other = dict(self.raw, regional='Cundinamarca', numero='20', documento='222', nombre='Otro empleado')
        self.db.save(other)
        self.assertEqual(len(self.db.search(regional='Bogotá')), 1)
        self.assertEqual(len(self.db.search(regional='Cundinamarca')), 1)
        self.assertEqual(len(self.db.search('Otro empleado', regional='Bogotá')), 0)
        self.assertEqual(len(self.db.search('Otro empleado', regional='Cundinamarca')), 1)
        self.assertEqual(self.db.region_counts(), {'Bogotá': 1, 'Cundinamarca': 1, '': 0})
        with self.assertRaises(ValidationError):
            self.db.save(dict(other, regional=''))
        with self.assertRaises(ValidationError):
            self.db.save(dict(other, regional='Otra'))

    def test_demo_isolated_and_complete(self):
        from datos_demo import seed_demo
        with closing(Database(Path(self.temp.name)/'demo.db')) as demo:
            seed_demo(demo)
            seed_demo(demo)
            self.assertEqual(len(demo.search()), 12)
            self.assertEqual(demo.region_counts(), {'Bogotá': 8, 'Cundinamarca': 8, '': 0})
            for row in demo.search():
                for key, _, _ in FIELDS:
                    if key != 'fecha_fin':
                        self.assertTrue(row[key], key)
        self.assertEqual(len(self.db.search()), 0)

    def test_migrate_old_database_without_guessing_region(self):
        from talento_humano import KEYS
        old_path = Path(self.temp.name)/'old.db'
        old_keys = [k for k in KEYS if k != 'regional']
        columns = ', '.join(f"{key} TEXT NOT NULL DEFAULT ''" for key in old_keys)
        data = validate(self.raw)
        with closing(sqlite3.connect(old_path)) as old:
            old.execute(f'''CREATE TABLE empleados (id INTEGER PRIMARY KEY, {columns},
                version INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL,
                actualizado TEXT NOT NULL, UNIQUE(numero), UNIQUE(documento))''')
            old.execute(f"INSERT INTO empleados ({', '.join(old_keys)}, creado, actualizado) VALUES ({', '.join('?' for _ in range(len(old_keys)+2))})",
                        [data[k] for k in old_keys]+['2026-01-01','2026-01-01'])
            old.commit()
        with closing(Database(old_path)) as migrated:
            row = migrated.search(regional='')[0]
            for key in old_keys:
                self.assertEqual(row[key], data[key])
            self.assertEqual(len(migrated.search(regional='Bogotá')), 0)
            migrated.save(self.raw, row['id'], row['version'])
            self.assertEqual(len(migrated.search(regional='Bogotá')), 1)
        backups = list(Path(self.temp.name).glob('old_antes_actualizacion_*.db'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as backup:
            self.assertNotIn('regional', [r[1] for r in backup.execute('PRAGMA table_info(empleados)')])

    def test_excel_aliases_and_values(self):
        from importar_excel import suggest_mapping, cell_text
        from openpyxl.cell.cell import Cell
        from openpyxl.utils.datetime import WINDOWS_EPOCH
        from types import SimpleNamespace
        headers = ['No', 'DOCUMENTO', 'NOMBRE', 'T. CONTREATO', 'N° DE CUENTA', 'T. CUENTA', 'FECHA EXPEDICION DEL DCTO']
        mapping = suggest_mapping(headers)
        self.assertEqual(mapping, {'numero': 0, 'documento': 1, 'nombre': 2,
                                 'tipo_contrato': 3, 'cuenta': 4, 'tipo_cuenta': 5,
                                 'fecha_expedicion': 6})
        def cell(value, fmt='General'):
            return SimpleNamespace(value=value, data_type='n', number_format=fmt)
        self.assertEqual(cell_text(cell(123, '000000'), 'cuenta', WINDOWS_EPOCH), '000123')
        self.assertEqual(cell_text(cell('$ 1.500.000,50'), 'salario', WINDOWS_EPOCH), '1500000,50')
        self.assertEqual(cell_text(cell('2026-10-20'), 'fecha_contrato', WINDOWS_EPOCH), '20/10/2026')
        self.assertEqual(cell_text(cell('Femenino'), 'sexo', WINDOWS_EPOCH), 'F')
        self.assertEqual(cell_text(cell(2), 'riesgo', WINDOWS_EPOCH), '2')
        with self.assertRaises(ValueError):
            cell_text(cell(1234567890123456), 'cuenta', WINDOWS_EPOCH)

    def test_automatic_numbers_and_preserved_excel_numbers(self):
        first = self.db.save(dict(self.raw, numero=''))
        self.assertEqual(self.db.get(first)['numero'], '1')
        rows = [(2, dict(self.raw, numero='', documento='AUTO-2')),
                (3, dict(self.raw, numero='0009', documento='EXCEL-9'))]
        self.assertEqual(self.db.import_rows(rows), (2, 0))
        self.assertEqual(self.db.search('AUTO-2')[0]['numero'], '10')
        self.assertEqual(self.db.search('EXCEL-9')[0]['numero'], '0009')
        self.assertEqual(self.db.import_rows(rows), (0, 2))
        third = self.db.save(dict(self.raw, numero='', documento='AUTO-3'))
        self.assertEqual(self.db.get(third)['numero'], '11')

    def test_salary_display_and_prorroga(self):
        row = self.db.get(self.db.save(dict(self.raw, salario='1800000')))
        self.assertEqual(row['salario'], '1800000')
        self.assertEqual(display('salario', row['salario']), '1.800.000')
        self.assertEqual(display('salario', '1800000.50'), '1.800.000,50')
        self.assertEqual(row['prorroga1'], '2027-02-01')
        self.assertEqual(display('prorroga1', row['prorroga1']), '01/02/2027')

    def test_roman_risk_migration_preserves_backup(self):
        employee = self.db.save(self.raw)
        self.db.conn.execute("UPDATE empleados SET riesgo='IV' WHERE id=?", (employee,))
        self.db.conn.commit()
        path = self.db.path
        self.db.close()
        self.db = Database(path)
        self.assertEqual(self.db.get(employee)['riesgo'], '4')
        copies = list(path.parent.glob('test_antes_*'))
        self.assertEqual(len(copies), 1)
        with closing(sqlite3.connect(copies[0])) as backup:
            self.assertEqual(backup.execute('SELECT riesgo FROM empleados').fetchone()[0], 'IV')

    def test_colombian_catalogs_include_both_regions(self):
        from catalogos import MUNICIPIOS, LISTAS
        self.assertGreater(len(MUNICIPIOS), 1100)
        self.assertEqual(len({r['codigo'] for r in MUNICIPIOS}), len(MUNICIPIOS))
        self.assertTrue(any(r['codigo']=='11001' for r in MUNICIPIOS))
        self.assertTrue(any(r['municipio']=='Cajicá' and r['departamento']=='Cundinamarca' for r in MUNICIPIOS))
        for key in ('eps', 'afp', 'cesantias', 'entidad_financiera'):
            self.assertGreater(len(LISTAS[key]), 4)

    def multi(self):
        from datos_demo import demo_records
        return dict(list(demo_records())[2])

    def test_both_regions_no_duplicate_and_same_assignment_filters(self):
        raw = self.multi()
        employee_id = self.db.save(raw)
        self.assertEqual(len(self.db.search()), 1)
        self.assertEqual([r['id'] for r in self.db.search(regional='Bogotá')], [employee_id])
        self.assertEqual([r['id'] for r in self.db.search(regional='Cundinamarca')], [employee_id])
        self.assertEqual(len(self.db.search(regional='Bogotá',sede='Redentor',perfil='Psicólogo')),1)
        self.assertEqual(len(self.db.search(regional='Cundinamarca',sede='Redentor')),0)
        self.assertEqual(len(self.db.search(sede='Cajica',perfil='Psicólogo')),0)
        self.assertEqual(len(self.db.search('Cárdenas Camila',tipo_contrato='Definido')),1)
        self.assertEqual(len(self.db.search('Camila inexistente')),0)

    def test_profiles_same_site_modality_and_exact_total(self):
        raw = self.multi()
        employee_id = self.db.save(raw)
        rows = self.db.assignments(employee_id)
        self.assertEqual(len(rows),3)
        self.assertEqual({r['perfil'] for r in rows if r['sede']=='Redentor'}, {'Gestor','Psicólogo'})
        self.assertEqual(self.db.conn.execute('SELECT sum(horas_centesimas) FROM asignaciones').fetchone()[0],4000)
        raw['_asignaciones'][0]['horas']='12,25'
        raw['_asignaciones'][1]['horas']='7,75'
        self.db.save(raw,employee_id,1)
        self.assertEqual(self.db.conn.execute('SELECT sum(horas_centesimas) FROM asignaciones').fetchone()[0],4000)

    def test_invalid_distribution_is_atomic(self):
        from copy import deepcopy
        original = self.multi()
        employee_id = self.db.save(original)
        for change in ('total','region','modalidad','duplicate','negative','missing_region'):
            raw=deepcopy(original)
            if change=='total':raw['horas_totales']='41'
            elif change=='region':raw['regional']='Bogotá'
            elif change=='modalidad':raw['_asignaciones'][2]['modalidad']='CAE 27'
            elif change=='duplicate':raw['_asignaciones'][1]['perfil']='Gestor'
            elif change=='negative':raw['_asignaciones'][0]['horas']='-1'
            elif change=='missing_region':raw['_asignaciones']=raw['_asignaciones'][:2];raw['horas_totales']='20'
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.db.save(raw,employee_id,1)
            self.assertEqual(self.db.get(employee_id)['version'],1)
            self.assertEqual(len(self.db.assignments(employee_id)),3)
        self.assertEqual(self.db.conn.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_assignment_updates_concurrency_and_reopen(self):
        raw=self.multi()
        employee_id=self.db.save(raw)
        raw['regional']='Bogotá';raw['horas_totales']='20';raw['_asignaciones']=raw['_asignaciones'][:2]
        self.db.save(raw,employee_id,1)
        with self.assertRaises(ValueError):self.db.save(self.multi(),employee_id,1)
        path=self.db.path;self.db.close();self.db=Database(path)
        self.assertEqual(len(self.db.assignments(employee_id)),2)
        self.assertEqual(len(self.db.search(regional='Cundinamarca')),0)
        self.assertEqual(self.db.get(employee_id)['sede'],'Redentor')
        with closing(sqlite3.connect(path)) as other:
            self.assertEqual(other.execute('SELECT count(*) FROM empleado_regionales').fetchone()[0],1)

    def test_names_alphabetical_and_original_preserved(self):
        for i,(last,first) in enumerate([('Ñúñez Prueba','Eva'),('Núñez Ejemplo','Luis'),('Álvarez Ficticio','Ana')]):
            self.db.save(dict(self.raw,numero=str(i+1),documento=str(i+100),apellidos=last,nombres=first,nombre=first+' '+last))
        rows=self.db.search()
        self.assertEqual([r['nombre'] for r in rows], ['Álvarez Ficticio Ana','Núñez Ejemplo Luis','Ñúñez Prueba Eva'])
        self.assertEqual(rows[0]['nombre_original'],'Ana Álvarez Ficticio')
        legacy=self.db.save(dict(self.raw,numero='99',documento='999',nombre='María del Carmen de la Cruz'))
        self.assertEqual(self.db.get(legacy)['nombre'],'María del Carmen de la Cruz')
        self.assertEqual([r['id'] for r in self.db.search(pendientes='Nombres por revisar')],[legacy])

    def test_bank_automatic_and_imported_code_preserved(self):
        from catalogos import BANK_CODES, bank_code
        self.assertEqual(bank_code('Bancolombia'),'1007')
        self.assertEqual(bank_code('Davivienda'),'1051')
        for name,code in BANK_CODES.items():
            self.assertEqual(validate(dict(self.raw,entidad_financiera=name,codigo_banco=''))['codigo_banco'],code)
        self.assertEqual(validate(dict(self.raw,entidad_financiera='Bancolombia',codigo_banco='007'))['codigo_banco'],'007')
        self.assertEqual(bank_code('Entidad no reconocida'),'')

    def test_import_relations_duplicates_and_rollback(self):
        from copy import deepcopy
        raw=self.multi()
        self.assertEqual(self.db.import_rows([(2,raw)]),(1,0))
        self.assertEqual(self.db.import_rows([(2,raw)]),(0,1))
        new=deepcopy(raw);new['numero']='99';new['documento']='NEW'
        invalid=deepcopy(raw);invalid['_asignaciones'][0]['perfil']='Otro'
        with self.assertRaises(ValueError):self.db.import_rows([(3,new),(4,invalid)])
        self.assertEqual(len(self.db.search()),1)
        self.assertEqual(len(self.db.assignments(self.db.search()[0]['id'])),3)

    def test_migration_previous_34_field_schema(self):
        import json
        from talento_humano import KEYS
        path=Path(self.temp.name)/'v1.db'
        old_keys=[k for k in KEYS if k not in ('apellidos','nombres','modalidad','horas_totales','periodo_horas')]
        columns=', '.join(f"{key} TEXT NOT NULL DEFAULT ''" for key in old_keys)
        data=validate(self.raw)
        with closing(sqlite3.connect(path)) as old:
            old.execute(f"CREATE TABLE empleados (id INTEGER PRIMARY KEY,{columns},version INTEGER DEFAULT 1,creado TEXT,actualizado TEXT,UNIQUE(numero),UNIQUE(documento))")
            old.execute(f"INSERT INTO empleados ({','.join(old_keys)}) VALUES ({','.join('?' for _ in old_keys)})",[data[k] for k in old_keys]);old.commit()
        with closing(Database(path)) as migrated:
            row=migrated.get(1)
            for key in old_keys:self.assertEqual(row[key],data[key])
            self.assertEqual(row['nombre_original'],data['nombre'])
            self.assertEqual(migrated.assignments(1),[])
            self.assertEqual(len(migrated.search(regional='Bogotá')),1)
        self.assertEqual(len(list(path.parent.glob('v1_antes_actualizacion_*'))),1)
        with closing(Database(path)) as reopened:self.assertEqual(len(reopened.search()),1)
        self.assertEqual(len(list(path.parent.glob('v1_antes_actualizacion_*'))),1)

    def test_excel_names_and_assignment_sheet(self):
        from openpyxl import Workbook
        from importar_excel import ExcelSource,suggest_mapping
        path=Path(self.temp.name)/'relaciones.xlsx'
        book=Workbook();sheet=book.active;sheet.title='Empleados'
        sheet.append(['Documento','Apellidos','Nombres','Regional','Horas totales','Periodo'])
        sheet.append(['DEMO-99','Godoy Ejemplo','Nicolas','Ambas',40,'Semanales'])
        assignments=book.create_sheet('Asignaciones')
        assignments.append(['Documento','Regional','Sede','Modalidad','Perfil','Horas'])
        assignments.append(['DEMO-99','Bogotá','Redentor','CAE MASCULINO REDENTOR','Gestor',12])
        assignments.append(['DEMO-99','Bogotá','Redentor','CAE MASCULINO REDENTOR','Psicólogo',8])
        assignments.append(['DEMO-99','Cundinamarca','Cajica','CAE FEMENINO','Psicólogo',20])
        book.save(path);book.close()
        source=ExcelSource(path)
        try:
            mapping=suggest_mapping(source.headers('Empleados',1))
            rows,errors=source.records('Empleados',1,mapping)
            self.assertEqual(errors,[])
            self.assertEqual(self.db.import_rows(rows),(1,0))
            row=self.db.search()[0]
            self.assertEqual(row['nombre'],'Godoy Ejemplo Nicolas')
            self.assertEqual(len(self.db.assignments(row['id'])),3)
        finally:source.close()

    def test_excel_reader_fixture(self):
        # XLSX sintético mínimo: dos filas; prueba lectura real, sin datos personales.
        from zipfile import ZipFile
        from importar_excel import ExcelSource, suggest_mapping
        path = Path(self.temp.name) / 'fixture.xlsx'
        xml = '<?xml version="1.0" encoding="UTF-8"?>'
        files = {
            '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
            '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Empleados" sheetId="1" r:id="rId1"/></sheets></workbook>',
            'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        }
        def text_cell(ref, text):
            return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'
        headers = ''.join(text_cell(c+'1', text) for c, text in zip('ABCDE', ['No', 'DOCUMENTO', 'NOMBRE', 'N° DE CUENTA', 'REGIONAL']))
        valid = ''.join(text_cell(c+'2', text) for c, text in zip('ABCDE', ['001', '0002', 'Persona de prueba', '000003', 'bogota']))
        formula = text_cell('A3','002') + text_cell('B3','0004') + '<c r="C3"><f>CONCAT("Persona", " prueba")</f></c>' + text_cell('E3', 'Cundinamarca')
        other = ''.join(text_cell(c+'4', text) for c, text in zip('ABCDE', ['003', '0005', 'Otra persona', '000006', 'Cundinamarca']))
        files['xl/worksheets/sheet1.xml'] = f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">{headers}</row><row r="2">{valid}</row><row r="3">{formula}</row><row r="4">{other}</row></sheetData></worksheet>'
        with ZipFile(path, 'w') as archive:
            for name, content in files.items():
                archive.writestr(name, xml + content)
        source = ExcelSource(path)
        try:
            mapping = suggest_mapping(source.headers('Empleados', 1))
            rows, errors = source.records('Empleados', 1, mapping, 'Bogotá')
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][1]['cuenta'], '000003')
            self.assertEqual(rows[0][1]['regional'], 'Bogotá')
            self.assertEqual(rows[1][1]['regional'], 'Cundinamarca')
            self.assertEqual(len(errors), 1)
            self.assertIn('Fila 3', errors[0])
            self.assertIn('fórmula', errors[0])
            without_number = {k: v for k, v in mapping.items() if k != 'numero'}
            unnumbered, _ = source.records('Empleados', 1, without_number, 'Bogotá')
            self.assertEqual(len(unnumbered), 2)
            self.assertNotIn('numero', unnumbered[0][1])
            mapping.pop('regional')
            default_rows, _ = source.records('Empleados', 1, mapping, 'Cundinamarca')
            self.assertTrue(all(r[1]['regional'] == 'Cundinamarca' for r in default_rows))
            with self.assertRaises(ValueError):
                source.records('Empleados', 1, mapping)
            with self.assertRaises(ValueError):
                source.records('Empleados', 1, {'numero': 0, 'documento': 0, 'nombre': 2}, 'Bogotá')
        finally:
            source.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
