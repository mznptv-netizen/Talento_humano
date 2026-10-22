"""Empleados completamente ficticios para una base de demostración independiente."""
from datetime import date, timedelta
from talento_humano import REGIONS
from relaciones import MODALIDADES, summary


def demo_records():
    names = [('Álvarez Ejemplo','Valentina','Gestor','F'),
             ('Beltrán Ficticio','Mateo','Psicólogo','M'),
             ('Cárdenas Prueba','Camila','Trabajador social','F'),
             ('Díaz Ejemplo','Samuel','Educador','M'),
             ('Espinosa Ficticia','Isabela','Auxiliar','F'),
             ('Fernández Prueba','Nicolás','Coordinador','M'),
             ('Gómez Ejemplo','Luciana','Psicólogo','F'),
             ('Herrera Ficticio','Daniel','Gestor','M'),
             ('Jiménez Prueba','Mariana','Auxiliar','F'),
             ('López Ejemplo','Sebastián','Educador','M'),
             ('Moreno Ficticia','Gabriela','Trabajador social','F'),
             ('Naranjo Prueba','Tomás','Coordinador','M')]
    today = date.today()
    for i, (last, first, role, sex) in enumerate(names):
        region = ('Bogotá','Cundinamarca','Ambas')[i % 3]
        if region == 'Ambas':
            assignments = [dict(regional='Bogotá',sede='Redentor',modalidad='CAE MASCULINO REDENTOR',perfil='Gestor',horas='12'),
                           dict(regional='Bogotá',sede='Redentor',modalidad='CAE MASCULINO REDENTOR',perfil='Psicólogo',horas='8'),
                           dict(regional='Cundinamarca',sede='Cajica',modalidad='CAE FEMENINO',perfil=role,horas='20')]
        else:
            assignments = [dict(regional=region,sede='Femenino',modalidad=MODALIDADES[region][0],perfil=role,horas='24'),
                           dict(regional=region,sede=('Cipla','Cetra')[i%2],modalidad=MODALIDADES[region][1],perfil='Gestor' if role != 'Gestor' else 'Psicólogo',horas='16')]
        code = {'Bogotá':'BOG','Cundinamarca':'CUN','Ambas':'AMB'}[region] + f'-{i + 1:03}'
        end = today + timedelta(days=(15, 90, 24, 180, -12, 365)[i % 6])
        yield {
            'regional': region, 'numero': str(i+1),
            'documento': 'FICTICIO-' + code, 'nombre': last+' '+first, 'apellidos': last, 'nombres': first,
            'sede': summary(assignments,'sede'), 'modalidad': summary(assignments,'modalidad'),
            'horas_totales': '40', 'periodo_horas':'Semanales', '_asignaciones': assignments,
            'fecha_ingreso': '15/01/2024', 'fecha_fin': end.strftime('%d/%m/%Y') if i % 2 == 0 else '',
            'cargo': role, 'direccion': f'Calle de ejemplo {i+1}, casa ficticia',
            'barrio': 'Barrio de demostración', 'ciudad': 'Cajicá (Cundinamarca)' if region == 'Cundinamarca' else 'Bogotá, D.C. (Bogotá, D.C.)',
            'fijo': f'000000{i+1:04}', 'celular': f'000000{i+1:04}',
            'correo': f'empleado.demo{i+1}@example.com', 'eps': 'Nueva EPS',
            'afp': 'Porvenir', 'cesantias': 'Protección',
            'riesgo': ('1', '2', '3')[i % 3], 'salario': str(2200000 + i * 175000),
            'fecha_nacimiento': f'{i+1:02}/06/1992', 'lugar_nacimiento': 'Bogotá, D.C. (Bogotá, D.C.)',
            'fecha_expedicion': f'{i+1:02}/07/2010', 'lugar_expedicion': 'Bogotá, D.C. (Bogotá, D.C.)',
            'rh': ('O+', 'A+', 'B+', 'AB+')[i % 4], 'sexo': sex,
            'estatura': str(158 + i * 2), 'entidad_financiera': 'Bancolombia',
            'codigo_banco': '1007', 'cuenta': f'DEMO-{i+1:010}', 'tipo_cuenta': 'Ahorros',
            'datos_actualizados': today.strftime('%d/%m/%Y'),
            'fecha_contrato': '15/01/2024', 'prorroga1': '15/01/2025',
            'tipo_contrato': ('Definido', 'Indefinido')[i % 2],
        }


def seed_demo(database):
    """Se llama únicamente con la base de demostración creada por la interfaz."""
    if not database.search():
        database.import_rows(list(enumerate(demo_records(), start=1)))
