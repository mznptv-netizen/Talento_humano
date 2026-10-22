"""Calendario y tabla de municipios para formularios CustomTkinter."""
import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from talento_humano import normalize
from catalogos import MUNICIPIOS

PINK = '#C52270'
MONTHS = ('Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre')


class ManagedEntry(ctk.CTkEntry):
    """Retira el observador al cerrar para permitir reutilizar StringVar."""
    def destroy(self):
        variable = self._textvariable
        callback = getattr(self, '_textvariable_callback_name', None)
        if isinstance(variable, tk.Variable) and callback:
            try:
                variable.trace_remove('write', callback)
            except tk.TclError:
                pass
            self._textvariable_callback_name = None
        super().destroy()


class PickerDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, size):
        super().__init__(parent)
        self.owner = parent.winfo_toplevel()
        self.title(title)
        self.geometry(size)
        self.configure(fg_color='#F5F6FA')
        self.transient(self.owner)
        self.grab_set()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Escape>', lambda e: self.close())

    def close(self):
        self.destroy()
        if self.owner.winfo_exists():
            self.owner.grab_set()


class CalendarDialog(PickerDialog):
    def __init__(self, parent, variable):
        super().__init__(parent, 'Seleccionar fecha', '450x440')
        self.variable = variable
        try:
            current = datetime.strptime(variable.get(), '%d/%m/%Y').date()
        except ValueError:
            current = date.today()
        self.month = tk.StringVar(value=MONTHS[current.month-1])
        self.year = tk.StringVar(value=str(current.year))
        bar = ctk.CTkFrame(self, fg_color='transparent')
        bar.pack(fill='x', padx=18, pady=18)
        for text, step in [('‹', -1), ('›', 1)]:
            ctk.CTkButton(bar, text=text, width=32, fg_color=PINK, command=lambda n=step: self.move(n)).pack(side='left' if step==-1 else 'right', padx=3)
        ctk.CTkComboBox(bar, values=list(MONTHS), variable=self.month, state='readonly', width=135, command=lambda v: self.draw()).pack(side='left', padx=4)
        years = [str(y) for y in range(min(1900,current.year),max(date.today().year+51,current.year+1))]
        ctk.CTkComboBox(bar, values=years, variable=self.year, state='readonly', width=90, command=lambda v: self.draw()).pack(side='left', padx=4)
        self.days = ctk.CTkFrame(self, fg_color='white', corner_radius=12)
        self.days.pack(fill='both', expand=True, padx=18)
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(fill='x', padx=18, pady=16)
        ctk.CTkButton(footer, text='Hoy', width=110, fg_color=PINK, command=lambda:self.choose(date.today())).pack(side='left')
        ctk.CTkButton(footer, text='Borrar fecha', width=130, fg_color='#6B677D', command=self.clear).pack(side='right')
        self.draw()

    def move(self, step):
        total = int(self.year.get())*12 + MONTHS.index(self.month.get()) + step
        year, month = divmod(total,12)
        if not 1 <= year <= 9999:
            return
        self.year.set(str(year));self.month.set(MONTHS[month]);self.draw()

    def draw(self):
        for child in self.days.winfo_children(): child.destroy()
        self.days.grid_columnconfigure(tuple(range(7)), weight=1)
        for col, name in enumerate(('L','M','M','J','V','S','D')):
            ctk.CTkLabel(self.days, text=name, text_color='#77758A').grid(row=0,column=col,pady=5)
        year, month = int(self.year.get()), MONTHS.index(self.month.get())+1
        for row, week in enumerate(calendar.monthcalendar(year,month),start=1):
            for col, day in enumerate(week):
                if day:
                    value=date(year,month,day)
                    ctk.CTkButton(self.days, text=str(day), width=42, height=32, corner_radius=8,
                        fg_color=PINK if value==date.today() else '#FCECF3', text_color='white' if value==date.today() else '#242338',
                        hover_color='#E6B8CF',command=lambda v=value:self.choose(v)).grid(row=row,column=col,padx=3,pady=3)

    def choose(self, value):
        self.variable.set(value.strftime('%d/%m/%Y'));self.close()

    def clear(self):
        self.variable.set('');self.close()


class MunicipalityDialog(PickerDialog):
    def __init__(self, parent, variable):
        super().__init__(parent, 'Municipios de Colombia', '760x580')
        self.variable=variable
        self.query=tk.StringVar()
        self.department=tk.StringVar(value='Todos los departamentos')
        ctk.CTkLabel(self,text='Elige ciudad o municipio',font=('Segoe UI',22,'bold')).pack(anchor='w',padx=22,pady=(18,10))
        ManagedEntry(self,textvariable=self.query,placeholder_text='Buscar municipio, departamento o código…',height=38).pack(fill='x',padx=22)
        ctk.CTkComboBox(self,values=['Todos los departamentos',*sorted({r['departamento'] for r in MUNICIPIOS})],variable=self.department,state='readonly',command=lambda v:self.refresh(),width=350).pack(anchor='w',padx=22,pady=10)
        frame=ctk.CTkFrame(self,fg_color='white');frame.pack(fill='both',expand=True,padx=22)
        self.tree=ttk.Treeview(frame,columns=('municipio','departamento','codigo'),show='headings',selectmode='browse',style='Team.Treeview')
        for key,caption,width in [('municipio','Municipio',290),('departamento','Departamento',240),('codigo','Código DANE',100)]:
            self.tree.heading(key,text=caption);self.tree.column(key,width=width,minwidth=70)
        scrollbar=ctk.CTkScrollbar(frame,command=self.tree.yview)
        scrollbar.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(fill='both',expand=True)
        self.tree.bind('<Double-1>',lambda e:self.choose());self.tree.bind('<Return>',lambda e:self.choose())
        footer=ctk.CTkFrame(self,fg_color='transparent');footer.pack(fill='x',padx=22,pady=16)
        ctk.CTkButton(footer,text='Usar municipio seleccionado',command=self.choose,fg_color=PINK,height=38).pack(side='right')
        ctk.CTkButton(footer,text='Borrar lugar',command=self.clear,fg_color='#6B677D',height=38).pack(side='left')
        self.query.trace_add('write',lambda *a:self.refresh())
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        query=normalize(self.query.get())
        for i,row in enumerate(MUNICIPIOS):
            if self.department.get() not in ('Todos los departamentos',row['departamento']):continue
            if query not in normalize(' '.join(row.values())):continue
            self.tree.insert('', 'end',iid=str(i),values=[row[k] for k in ('municipio','departamento','codigo')])

    def clear(self):
        self.variable.set('');self.close()

    def choose(self):
        selected=self.tree.selection()
        if selected:
            row=MUNICIPIOS[int(selected[0])]
            self.variable.set(f"{row['municipio']} ({row['departamento']})")
            self.close()


class PickerField(ctk.CTkFrame):
    def __init__(self,parent,variable,kind='date',editable=False):
        super().__init__(parent,fg_color='transparent')
        self.variable,self.kind=variable,kind
        self.grid_columnconfigure(0,weight=1)
        self.entry=ManagedEntry(self,textvariable=variable,height=40,fg_color='#F5F6FA',border_color='#E8E7F0',state='normal' if editable else 'readonly')
        self.entry.grid(row=0,column=0,sticky='ew')
        ctk.CTkButton(self,text='Calendario' if kind=='date' else 'Elegir',command=self.open,width=92,height=40,fg_color=PINK).grid(row=0,column=1,padx=(6,0))

    def open(self):
        return (CalendarDialog if self.kind=='date' else MunicipalityDialog)(self,self.variable)
