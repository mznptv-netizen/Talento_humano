"""Interfaz moderna de Talento Humano: regionales, tabla completa y fichas."""
from pathlib import Path
from datetime import date, datetime
import sqlite3
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from PIL import Image, ImageTk
from talento_humano import Database, FIELDS, KEYS, LABELS, DATES, REQUIRED, CHOICES, REGIONS, display, ValidationError, normalize
from datos_demo import seed_demo
from catalogos import LISTAS, bank_code
from asignaciones_ui import AssignmentPanel
from relaciones import REGIONAL_OPTIONS, SEDES, modalities, summary, hours_text, hundredths
from selectores import PickerField, ManagedEntry

BG = '#F5F6FA'
WHITE = '#FFFFFF'
INK = '#242338'
MUTED = '#77758A'
LINE = '#E8E7F0'
PINK = '#C52270'
PINK_HOVER = '#A91A5E'
PALE = '#FCECF3'
TEAL = '#157D70'
GROUPS = ('Personal', 'Laboral', 'Asignaciones', 'Contacto', 'Afiliaciones', 'Bancarios')
DIRECTORY = ('nombre', 'documento', 'regional', 'sede', 'modalidad', 'horas_totales', 'cargo', 'celular')
ALL_COLUMNS = ('nombre', 'documento', 'regional', 'sede', 'modalidad', 'horas_totales', 'numero') + tuple(k for k in KEYS if k not in ('nombre', 'documento', 'regional', 'sede', 'modalidad', 'horas_totales', 'numero'))


def label(parent, text='', size=14, color=INK, bold=False, **kwargs):
    return ctk.CTkLabel(parent, text=text, text_color=color,
                        font=ctk.CTkFont(family='Segoe UI', size=size, weight='bold' if bold else 'normal'), **kwargs)


def button(parent, text, command, primary=False, **kwargs):
    return ctk.CTkButton(parent, text=text, command=command, height=40,
                         corner_radius=10, fg_color=PINK if primary else WHITE,
                         hover_color=PINK_HOVER if primary else PALE,
                         text_color=WHITE if primary else INK,
                         border_width=0 if primary else 1, border_color=LINE,
                         font=ctk.CTkFont(family='Segoe UI', size=13, weight='bold'), **kwargs)


def modal(window, app, width=960, height=740):
    window.transient(app)
    width = min(width, app.winfo_screenwidth() - 60)
    height = min(height, app.winfo_screenheight() - 80)
    window.geometry(f'{width}x{height}')
    window.minsize(min(800, width), min(580, height))
    window.configure(fg_color=BG)
    window.grab_set()


class EmployeeDetails(ctk.CTkToplevel):
    def __init__(self, app, record):
        super().__init__(app)
        self.app, self.record = app, record
        self.title('Ficha completa | ' + record['nombre'])
        modal(self, app)
        self.field_widgets = {}
        top = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0)
        top.pack(fill='x')
        label(top, 'FICHA DEL EMPLEADO  /  ' + (record['regional'] or 'Por asignar'), 12, PINK, True).pack(anchor='w', padx=28, pady=(18, 2))
        label(top, record['nombre'], 26, bold=True).pack(anchor='w', padx=28)
        label(top, f'{len(FIELDS)} campos · Ficha y distribución completa de horas', 13, MUTED).pack(anchor='w', padx=28, pady=(3, 16))
        footer = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0)
        footer.pack(side='bottom', fill='x')
        button(footer, 'Editar empleado', self.edit, primary=True).pack(side='right', padx=(8, 24), pady=14)
        button(footer, 'Cerrar ficha', self.destroy).pack(side='right', pady=14)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self.scroll.pack(fill='both', expand=True, padx=16, pady=10)
        self.scroll.columnconfigure(0, weight=1)
        for section, group in enumerate(GROUPS):
            card = ctk.CTkFrame(self.scroll, fg_color=WHITE, corner_radius=14, border_color=LINE, border_width=1)
            card.grid(row=section, column=0, sticky='ew', pady=(0, 12), padx=4)
            card.columnconfigure((0, 1), weight=1, uniform='detail')
            label(card, group, 17, PINK, True).grid(row=0, column=0, columnspan=2, sticky='w', padx=22, pady=(16, 8))
            fields = [(k, caption) for k, caption, g in FIELDS if g == group]
            for i, (key, caption) in enumerate(fields):
                cell = ctk.CTkFrame(card, fg_color='transparent')
                cell.grid(row=i//2+1, column=i%2, sticky='new', padx=22, pady=(5, 16))
                label(cell, caption, 12, MUTED).pack(anchor='w')
                text = display(key, record[key]) or 'Sin registrar'
                value = label(cell, text, 15, bold=True, anchor='w', justify='left', wraplength=300)
                value.pack(anchor='w', fill='x', pady=(2, 0))
                self.field_widgets[key] = value

        assignments = app.db.assignments(record['id'])
        card = ctk.CTkFrame(self.scroll, fg_color=WHITE, corner_radius=14)
        card.grid(row=len(GROUPS), column=0, sticky='ew', padx=4, pady=12)
        label(card, 'Distribución de horas y perfiles', 18, PINK, True).pack(anchor='w', padx=22, pady=14)
        if not assignments:
            label(card, 'Pendiente de registrar la distribución de horas.', 14, MUTED).pack(anchor='w',padx=22,pady=14)
        for item in assignments:
            text = f"{item['regional']} · {item['sede']} · {item['modalidad']}\n{item['perfil']} — {item['horas']} horas {record['periodo_horas'].lower()}"
            label(card,text,14,justify='left',wraplength=780).pack(anchor='w',padx=22,pady=(0,16))
        if not record['apellidos'] or not record['nombres']:
            label(card, 'Nombre por revisar: abre Editar y separa apellidos y nombres.', 13, PINK, wraplength=780).pack(anchor='w',padx=22,pady=14)

    def edit(self):
        record = self.app.db.get(self.record['id'])
        self.destroy()
        EmployeeEditor(self.app, record)


class EmployeeEditor(ctk.CTkToplevel):
    def __init__(self, app, record=None):
        super().__init__(app)
        self.app, self.record = app, record
        self.title('Editar empleado' if record else 'Nuevo empleado')
        modal(self, app)
        self.protocol('WM_DELETE_WINDOW', self.cancel)
        self.vars, self.widgets, self.tabs = {}, {}, {}
        for key in KEYS:
            value = (record[key] if key == 'salario' else display(key, record[key])) if record else (app.active_region if key == 'regional' and app.active_region in REGIONS else '')
            self.vars[key] = tk.StringVar(value=value)
        label(self, self.title(), 26, bold=True).pack(anchor='w', padx=26, pady=(22, 2))
        label(self, '* Obligatorio · Nombres por apellidos · Distribuye todas las horas en Asignaciones', 13, MUTED).pack(anchor='w', padx=26, pady=(0, 10))
        footer = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0)
        footer.pack(side='bottom', fill='x')
        button(footer, 'Guardar empleado', self.save, primary=True).pack(side='right', padx=(10, 24), pady=16)
        button(footer, 'Cancelar', self.cancel).pack(side='right', pady=16)
        self.notebook = ctk.CTkTabview(self, fg_color=WHITE, corner_radius=14,
            segmented_button_selected_color=PALE, segmented_button_selected_hover_color='#F7DCE8',
            segmented_button_unselected_color='#EEEDF3', segmented_button_unselected_hover_color=PALE,
            text_color=INK, text_color_disabled=MUTED)
        self.notebook.pack(fill='both', expand=True, padx=24, pady=(0, 18))
        for group in GROUPS:
            tab = self.notebook.add(group)
            if group == 'Asignaciones':
                self.assignment_panel = AssignmentPanel(tab, self.vars, app.db.assignments(record['id']) if record else [])
                self.assignment_panel.pack(fill='both', expand=True)
                self.widgets.update(self.assignment_panel.widgets)
                self.tabs.update({k: group for k in self.assignment_panel.widgets})
                continue
            scroll = ctk.CTkScrollableFrame(tab, fg_color=WHITE, corner_radius=0)
            scroll.pack(fill='both', expand=True)
            scroll.columnconfigure((0, 1), weight=1, uniform='edit')
            fields = [(k, caption) for k, caption, g in FIELDS if g == group]
            for index, (key, caption) in enumerate(fields):
                area = ctk.CTkFrame(scroll, fg_color='transparent')
                area.grid(row=index//2, column=index%2, sticky='ew', padx=12, pady=(10, 8))
                label(area, caption + (' *' if key in REQUIRED else ''), 13, MUTED).pack(anchor='w')
                var = self.vars[key]
                value = var.get()
                if key in DATES or key == 'datos_actualizados':
                    widget = PickerField(area, var, editable=key == 'datos_actualizados')
                elif key in ('ciudad', 'lugar_nacimiento', 'lugar_expedicion'):
                    widget = PickerField(area, var, kind='municipality')
                elif key in CHOICES or key in LISTAS:
                    options = list(CHOICES[key] if key in CHOICES else LISTAS[key])
                    if value and value not in options:
                        options.append(value)  # Visible sin perder el valor histórico importado.
                    widget = ctk.CTkComboBox(area, variable=var, values=options, state='readonly',
                        height=40, border_color=LINE, button_color=PINK, button_hover_color=PINK_HOVER,
                        fg_color=BG, text_color=INK, dropdown_fg_color=WHITE, dropdown_text_color=INK)
                else:
                    widget = ManagedEntry(area, textvariable=var, height=40, border_color=LINE,
                                          fg_color=BG, text_color=INK, corner_radius=8)
                if key in ('nombre', 'numero'):
                    widget.configure(state='readonly')
                    if key == 'numero' and not record:
                        label(area, 'Se asigna automáticamente al guardar', 11, PINK).pack(anchor='w')
                widget.pack(fill='x', pady=(5, 0))
                self.widgets[key], self.tabs[key] = widget, group
            hints = {'Personal': 'Completa Apellidos y Nombres por separado; el nombre de consulta se forma automáticamente.', 'Laboral': 'N.º automático · Contrato definido o indefinido · Prórroga 1 es una fecha. Datos actualizados admite fecha o texto.',
                     'Bancarios': 'Al elegir banco se propone su código de 4 dígitos. Puedes ajustarlo al formato de tu nómina. Salario sin miles: 1800000.'}
            if group in hints:
                label(scroll, hints[group], 12, MUTED, wraplength=680).grid(row=(len(fields)+1)//2, column=0, columnspan=2, sticky='w', padx=12, pady=12)
        self.name_traces = [(k,self.vars[k].trace_add('write', self.update_name)) for k in ('apellidos','nombres')]
        self.widgets['entidad_financiera'].configure(command=self.bank_selected)
        self.initial = self.snapshot()
        self.bind('<Control-s>', lambda event: self.save())
        self.notebook.set('Personal')

    def destroy(self):
        for key, callback in getattr(self, 'name_traces', []):
            self.vars[key].trace_remove('write', callback)
        self.name_traces = []
        super().destroy()

    def update_name(self, *args):
        if self.vars['apellidos'].get().strip() or self.vars['nombres'].get().strip():
            self.vars['nombre'].set(' '.join((self.vars['apellidos'].get()+' '+self.vars['nombres'].get()).split()))

    def bank_selected(self, name):
        self.vars['codigo_banco'].set(bank_code(name))

    def snapshot(self):
        return ({k:v.get() for k,v in self.vars.items()}, [dict(r) for r in self.assignment_panel.rows])

    def save(self):
        try:
            if not self.vars['apellidos'].get().strip() or not self.vars['nombres'].get().strip():
                raise ValidationError('apellidos', 'Completa Apellidos y Nombres por separado.')
            try:
                assignments = self.assignment_panel.require_complete()
            except ValueError as error:
                raise ValidationError('asignaciones', str(error)) from error
            employee_id = self.app.db.save({k: v.get() for k, v in self.vars.items()},
                self.record['id'] if self.record else None,
                self.record['version'] if self.record else None, assignments=assignments)
        except ValidationError as error:
            self.notebook.set('Asignaciones' if error.key == 'asignaciones' else self.tabs[error.key])
            if error.key in self.widgets:
                self.widgets[error.key].focus_set()
            messagebox.showwarning('Revisa este dato', str(error), parent=self)
            return
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror('No se pudo guardar', str(error), parent=self)
            return
        self.app.show_home()
        if self.app.tree.exists(str(employee_id)):
            self.app.tree.selection_set(str(employee_id))
            self.app.tree.see(str(employee_id))
        self.app.status.set('Empleado guardado correctamente.')
        self.destroy()

    def cancel(self):
        if self.initial != self.snapshot() or self.assignment_panel.pending_form():
            if not messagebox.askyesno('Cambios sin guardar', '¿Descartar los cambios de esta ficha?', parent=self):
                return
        self.destroy()


class AdvancedSearch(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title('Búsqueda avanzada')
        modal(self, app, 850, 620)
        label(self, 'Combinar filtros de empleados', 24, bold=True).pack(anchor='w',padx=26,pady=(22,8))
        label(self,'Sede, modalidad y perfil deben coincidir en una misma asignación.',13,MUTED).pack(anchor='w',padx=26,pady=(0,12))
        body=ctk.CTkFrame(self,fg_color=WHITE);body.pack(fill='both',expand=True,padx=24)
        body.columnconfigure((0,1),weight=1)
        options={'sede':['',*SEDES], 'modalidad':['',*modalities(app.active_region or 'Ambas')],
                 'tipo_contrato':['','Definido','Indefinido'],
                 'pendientes':['','Nombres por revisar','Sin distribución de horas']}
        self.vars={}
        captions=(('documento','Documento contiene'),('perfil','Perfil profesional contiene'),('sede','Sede'),
                  ('modalidad','Modalidad'),('tipo_contrato','Tipo de contrato'),('pendientes','Datos pendientes'))
        for i,(key,caption) in enumerate(captions):
            area=ctk.CTkFrame(body,fg_color='transparent');area.grid(row=i//2,column=i%2,sticky='ew',padx=18,pady=12)
            label(area,caption,13,MUTED).pack(anchor='w')
            var=tk.StringVar(value=app.advanced.get(key,''));self.vars[key]=var
            if key in options:
                widget=ctk.CTkComboBox(area,variable=var,values=options[key],state='readonly',height=38,button_color=PINK)
            else:widget=ManagedEntry(area,textvariable=var,height=38)
            widget.pack(fill='x',pady=4)
        footer=ctk.CTkFrame(self,fg_color='transparent');footer.pack(fill='x',padx=24,pady=18)
        button(footer,'Aplicar filtros',self.apply,primary=True).pack(side='right')
        button(footer,'Limpiar filtros',self.clear).pack(side='left')

    def apply(self):
        self.app.advanced={k:v.get().strip() for k,v in self.vars.items()}
        self.app.refresh();self.destroy()

    def clear(self):
        self.app.clear_search();self.destroy()


class App(ctk.CTk):
    def __init__(self, db):
        ctk.set_appearance_mode('light')
        super().__init__()
        self.real_db = self.db = db
        self.demo_db = None
        self.demo = False
        self.active_region = None
        self.advanced = {}
        self.query, self.site = tk.StringVar(), tk.StringVar(value='Todas las sedes')
        self.view = tk.StringVar(value='Todos los datos')
        self.status = tk.StringVar(value='Todos los empleados · Orden alfabético por apellidos.')
        self.tree = None
        self.sort_key, self.sort_reverse = 'nombre', False
        self.title('IPSICOL · Talento Humano')
        self.geometry(f'{min(1440,self.winfo_screenwidth()-60)}x{min(890,self.winfo_screenheight()-70)}')
        self.minsize(1050, 650)
        self.configure(fg_color=BG)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.setup_styles()
        self.sidebar = ctk.CTkScrollableFrame(self, width=222, fg_color=WHITE, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky='nsew')
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(8, weight=1)
        logo_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'logo_ipsicol.png'
        with Image.open(logo_path) as original:
            source = original.copy()
        self.logo = ctk.CTkImage(light_image=source, dark_image=source, size=(132, 132))
        self.window_icon = ImageTk.PhotoImage(source.resize((64, 64)))
        self.iconphoto(True, self.window_icon)
        ctk.CTkLabel(self.sidebar, image=self.logo, text='').grid(row=0, column=0, pady=(18, 0))
        label(self.sidebar, 'Talento Humano', 19, bold=True).grid(row=1, column=0, pady=(0, 6))
        label(self.sidebar, 'PERSONAS QUE TRANSFORMAN', 10, MUTED, True).grid(row=2, column=0, pady=(0, 26))
        button(self.sidebar, '+ Añadir empleado', self.new, primary=True, width=182).grid(row=3, column=0, padx=20, pady=(0, 10))
        button(self.sidebar, 'Inicio · Todos', self.show_home, width=182).grid(row=4, column=0, padx=20, pady=(0, 20))
        label(self.sidebar, 'FILTRAR POR REGIONAL', 11, MUTED, True, anchor='w').grid(row=5, column=0, sticky='ew', padx=25)
        nav = ctk.CTkFrame(self.sidebar, fg_color='transparent')
        nav.grid(row=6, column=0, sticky='ew', padx=16, pady=(10, 0))
        self.region_buttons = {}
        for region in (*REGIONS, ''):
            b = button(nav, region or 'Por asignar', lambda r=region: self.set_region(r), width=190, anchor='w')
            b.pack(fill='x', pady=4)
            self.region_buttons[region] = b
        label(self.sidebar, 'Ambas aparece en los\ndos filtros regionales.', 12, MUTED, justify='left').grid(row=7, column=0, sticky='w', padx=25, pady=18)
        lower = ctk.CTkFrame(self.sidebar, fg_color='transparent')
        lower.grid(row=9, column=0, sticky='ew', padx=16, pady=(10, 22))
        self.mode_badge = label(lower, '', 11, PINK, True, fg_color=PALE, corner_radius=8, height=32)
        self.mode_badge.pack(fill='x', pady=(0, 8))
        self.mode_button = button(lower, 'Probar con ejemplos', self.toggle_mode, width=190)
        self.mode_button.pack(fill='x', pady=4)
        button(lower, 'Copia de seguridad', self.backup, width=190).pack(fill='x', pady=4)
        button(lower, 'Dónde están mis datos', self.show_storage, width=190).pack(fill='x', pady=4)
        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky='nsew', padx=26, pady=24)
        if not self.real_db.search():
            self.activate_demo()
        self.show_home()

    def setup_styles(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('.', font=('Segoe UI', 10))
        s.configure('TFrame', background=BG)
        s.configure('TLabel', background=BG, foreground=INK)
        s.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        s.configure('TButton', background=WHITE, foreground=INK, padding=(12, 9), borderwidth=0)
        s.configure('Accent.TButton', background=PINK, foreground=WHITE)
        s.map('Accent.TButton', background=[('active', PINK_HOVER)])
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', padding=(16, 10))
        s.map('TNotebook.Tab', background=[('selected', PALE)], foreground=[('selected', PINK)])
        s.configure('Team.Treeview', rowheight=47, background=WHITE, fieldbackground=WHITE,
                     foreground=INK, font=('Segoe UI', 10), borderwidth=0)
        s.configure('Team.Treeview.Heading', background='#F2F1F7', foreground=MUTED,
                     font=('Segoe UI', 10, 'bold'), padding=(10, 14), borderwidth=0, relief='flat')
        s.configure('Assignments.Treeview', rowheight=30, font=('Segoe UI', 10), background=WHITE, fieldbackground=WHITE)
        s.configure('Assignments.Treeview.Heading', font=('Segoe UI',10,'bold'), background='#F2F1F7', foreground=MUTED, padding=(8,8), relief='flat')
        s.map('Assignments.Treeview', background=[('selected',PALE)],foreground=[('selected',INK)])
        s.map('Team.Treeview', background=[('selected', PALE)], foreground=[('selected', '#951951')])
        s.map('Team.Treeview.Heading', background=[('active', '#E9E6F0')])

    def activate_demo(self):
        if self.demo_db is None:
            self.demo_db = Database(self.real_db.path.parent / 'demostracion_ipsicol_v2.db')
            seed_demo(self.demo_db)
        self.db = self.demo_db
        self.demo = True

    def toggle_mode(self):
        if self.demo:
            self.db, self.demo = self.real_db, False
        else:
            self.activate_demo()
        if self.active_region is None:
            self.show_home()
        else:
            self.set_region(self.active_region)

    def update_sidebar(self):
        counts = self.db.region_counts()
        for region, b in self.region_buttons.items():
            b.configure(text=f'{region or "Por asignar"}    {counts.get(region,0)}',
                        fg_color=PINK if self.active_region == region else WHITE,
                        text_color=WHITE if self.active_region == region else INK,
                        hover_color=PINK_HOVER if self.active_region == region else PALE)
            if region == '' and not counts.get('', 0):
                b.pack_forget()
            elif not b.winfo_manager():
                b.pack(fill='x', pady=4)
        self.mode_badge.configure(text='DEMOSTRACIÓN · DATOS FICTICIOS' if self.demo else 'DATOS REALES · EQUIPO LOCAL',
                                  text_color=PINK if self.demo else TEAL, fg_color=PALE if self.demo else '#E6F5F0')
        self.mode_button.configure(text='Usar datos reales' if self.demo else 'Probar con ejemplos')

    def clear_main(self):
        self.tree = None
        for child in self.main.winfo_children():
            child.destroy()

    def show_home(self):
        self.set_region(None)

    def set_region(self, region):
        if region not in (None, *REGIONS, ''):
            raise ValueError('Regional no válida.')
        self.active_region = region
        self.query.set('')
        self.advanced = {}
        self.show_dashboard()

    def show_dashboard(self):
        self.clear_main()
        self.update_sidebar()
        header = ctk.CTkFrame(self.main, fg_color='transparent')
        header.pack(fill='x', pady=(0, 14))
        title = ctk.CTkFrame(header, fg_color='transparent')
        title.pack(side='left')
        label(title, 'TODOS LOS EMPLEADOS' if self.active_region is None else 'FILTRO  /  ' + (self.active_region or 'POR ASIGNAR'), 12, PINK, True).pack(anchor='w')
        label(title, 'Nuestro equipo', 30, bold=True).pack(anchor='w', pady=(2, 0))
        label(header, 'A–Z por apellidos', 13, MUTED).pack(side='right', pady=12)
        stats = ctk.CTkFrame(self.main, fg_color='transparent')
        stats.pack(fill='x', pady=(0, 16))
        stats.columnconfigure((0, 1, 2), weight=1, uniform='stats')
        self.stat_values = []
        for i, caption in enumerate(('Empleados en esta vista', 'Sedes registradas', 'Contratos por vencer · 30 días')):
            card = ctk.CTkFrame(stats, fg_color=WHITE, corner_radius=12, border_color=LINE, border_width=1)
            card.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 6, 0 if i == 2 else 6))
            label(card, caption, 12, MUTED).pack(anchor='w', padx=16, pady=(10, 0))
            val = label(card, '0', 27, PINK if i == 0 else INK, True)
            val.pack(anchor='w', padx=16, pady=(0, 10))
            self.stat_values.append(val)
        toolbar = ctk.CTkFrame(self.main, fg_color='transparent')
        toolbar.pack(fill='x', pady=(0, 10))
        search = ManagedEntry(toolbar, textvariable=self.query, placeholder_text='Buscar apellidos, nombres, documento, perfil…',
                              height=40, corner_radius=10, fg_color=WHITE, border_color=LINE, font=('Segoe UI', 13))
        search.pack(side='left', fill='x', expand=True, padx=(0, 8))
        search.bind('<Return>', lambda e: self.refresh())
        button(toolbar, 'Buscar', self.refresh, width=80).pack(side='left', padx=(0, 8))
        button(toolbar, 'Búsqueda avanzada', lambda: AdvancedSearch(self), width=160).pack(side='left', padx=(0, 8))
        self.import_button = button(toolbar, 'Importar Excel', self.import_excel, width=125)
        self.import_button.pack(side='left')
        if self.demo:
            self.import_button.configure(state='disabled')
        self.filter_note = label(self.main, '', 12, MUTED, anchor='w', wraplength=950)
        self.filter_note.pack(fill='x', pady=(0,8))
        strip = ctk.CTkFrame(self.main, fg_color='transparent')
        strip.pack(fill='x', pady=(0, 10))
        self.column_note = label(strip, '', 12, MUTED)
        self.column_note.pack(side='left')
        ctk.CTkSegmentedButton(strip, values=['Directorio', 'Todos los datos'], variable=self.view,
            command=lambda value: self.apply_view(), selected_color=PALE, selected_hover_color='#F7DCE8',
            unselected_color=WHITE, unselected_hover_color=PALE, fg_color=LINE, text_color=INK, height=34).pack(side='right')
        footer = ctk.CTkFrame(self.main, fg_color='transparent')
        footer.pack(side='bottom', fill='x', pady=(10, 0))
        self.selected_note = label(footer, 'Selecciona un empleado para ver su ficha.', 12, MUTED)
        self.selected_note.pack(side='left')
        button(footer, 'Ver ficha completa', self.details, primary=True, width=160).pack(side='right')
        button(footer, 'Editar', self.edit, width=80).pack(side='right', padx=8)
        self.count_label = label(self.main, '', 12, MUTED)
        self.count_label.pack(side='bottom', anchor='w', pady=(8, 0))
        table = ctk.CTkFrame(self.main, fg_color=WHITE, corner_radius=12, border_color=LINE, border_width=1)
        table.pack(fill='both', expand=True)
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=ALL_COLUMNS, show='headings', selectmode='browse', style='Team.Treeview')
        for key in ALL_COLUMNS:
            width = 245 if key in ('nombre', 'correo', 'direccion', 'cargo') else max(150, min(310, len(LABELS[key])*8+24))
            self.tree.heading(key, text=LABELS[key])
            self.tree.column(key, width=width, minwidth=90, stretch=False, anchor='w')
        v = ctk.CTkScrollbar(table, orientation='vertical', command=self.tree.yview, button_color='#C3BBCB', button_hover_color=PINK)
        h = ctk.CTkScrollbar(table, orientation='horizontal', command=self.tree.xview, button_color='#C3BBCB', button_hover_color=PINK, height=18)
        self.tree.configure(yscrollcommand=v.set, xscrollcommand=h.set)
        self.tree.grid(row=0, column=0, sticky='nsew', padx=(8, 0), pady=(8, 0))
        v.grid(row=0, column=1, sticky='ns', pady=(8, 0), padx=(0, 4))
        h.grid(row=1, column=0, sticky='ew', padx=8, pady=(0, 7))
        self.tree.tag_configure('alternate', background='#FAFAFD')
        self.tree.bind('<<TreeviewSelect>>', self.selection_changed)
        self.tree.bind('<Double-1>', lambda e: self.details())
        self.tree.bind('<Return>', lambda e: self.details())
        self.apply_view()
        self.refresh()

    def apply_view(self):
        if not self.tree:
            return
        self.tree.configure(displaycolumns=ALL_COLUMNS if self.view.get() == 'Todos los datos' else DIRECTORY)
        self.column_note.configure(text=f'{len(KEYS)} columnas · Desplázate horizontalmente para verlas todas' if self.view.get() == 'Todos los datos' else f'Vista rápida · Abre la ficha para consultar los {len(KEYS)} campos')
        self.tree.xview_moveto(0)

    def refresh(self):
        if self.tree is None:
            self.show_dashboard()
            return
        try:
            all_rows = self.db.search(regional=self.active_region)
            sites = {site.strip() for r in all_rows for site in r['sede'].split(';') if site.strip()}
            rows = self.db.search(self.query.get(), self.active_region, **self.advanced)
            expiring = sum(bool(r['fecha_fin']) and 0 <= (date.fromisoformat(r['fecha_fin'])-date.today()).days <= 30 for r in all_rows)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror('No se pudo consultar', str(error), parent=self)
            return
        pending = sum(not r['apellidos'] or not r['nombres'] for r in all_rows)
        filters = ' · '.join(f'{k.replace("_"," ")}: {v}' for k,v in self.advanced.items() if v)
        self.filter_note.configure(text=(filters or 'Sin filtros avanzados') + (f' · {pending} nombres por revisar' if pending else ''))
        for widget, value in zip(self.stat_values, (len(all_rows), len(sites), expiring)):
            widget.configure(text=f'{value:02}')
        selected = self.tree.selection()
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        for i, row in enumerate(rows):
            self.tree.insert('', 'end', iid=str(row['id']), values=[display(k, row[k]) for k in ALL_COLUMNS], tags=('alternate',) if i%2 else ())
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        text = f'{len(rows)} de {len(all_rows)} empleados · {'Todos' if self.active_region is None else (self.active_region or 'Pendientes de regional')}'
        if self.demo:
            text += ' · Ejemplos ficticios; cambia a datos reales para importar tu Excel.'
        self.count_label.configure(text=text)
        self.update_sidebar()

    def selection_changed(self, event=None):
        if self.tree is None:
            return
        selected = self.tree.selection()
        row = self.db.get(int(selected[0])) if selected else None
        self.selected_note.configure(text=(row['nombre'][:34] + ' · ' + (row['regional'] or 'Por asignar')) if row else 'Selecciona un empleado para ver su ficha.')

    def selected_record(self):
        if self.tree is None or not self.tree.selection():
            messagebox.showinfo('Selecciona un empleado', 'Haz clic en una fila del directorio.', parent=self)
            return None
        return self.db.get(int(self.tree.selection()[0]))

    def details(self):
        record = self.selected_record()
        if record:
            EmployeeDetails(self, record)

    def edit(self):
        record = self.selected_record()
        if record:
            EmployeeEditor(self, record)

    def new(self):
        EmployeeEditor(self)

    def clear_search(self):
        self.query.set('')
        self.advanced = {}
        self.refresh()

    def import_excel(self):
        if self.demo:
            messagebox.showinfo('Estás en demostración', 'Pulsa Usar datos reales antes de importar tu Excel.', parent=self)
            return
        from importar_excel import ImportDialog
        ImportDialog(self)

    def backup(self):
        prefix = 'DEMO_' if self.demo else 'Talento_Humano_'
        path = filedialog.asksaveasfilename(parent=self, title='Guardar copia de seguridad',
            initialfile=prefix+datetime.now().strftime('%Y%m%d_%H%M%S')+'.db',
            defaultextension='.db', filetypes=[('Base de datos SQLite', '*.db')])
        if path:
            try:
                self.db.backup(path)
                messagebox.showinfo('Copia creada', f'Se guardaron todos los empleados y sus asignaciones:\n{path}', parent=self)
            except (ValueError, OSError, sqlite3.Error) as error:
                messagebox.showerror('No se pudo crear la copia', str(error), parent=self)

    def show_storage(self):
        messagebox.showinfo('Dónde están mis datos', f'Base actual ({"demostración" if self.demo else "datos reales"}):\n{self.db.path}\n\nEl programa guarda los cambios en este equipo.', parent=self)

    def close(self):
        if self.demo_db:
            self.demo_db.close()
        self.real_db.close()
        self.destroy()
