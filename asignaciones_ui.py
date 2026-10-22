"""Editor de relaciones múltiples, con sumas exactas de horas."""
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from relaciones import (REGIONS, REGIONAL_OPTIONS, SEDES, PERIODOS, ASSIGNMENT_KEYS,
                         members, modalities, hundredths, hours_text, summary, canonical_assignments)
from selectores import ManagedEntry

PINK, BG, INK = '#C52270', '#F5F6FA', '#242338'


def combo(parent, variable, values, command=None):
    return ctk.CTkComboBox(parent, variable=variable, values=list(values), state='readonly',
                         command=command, height=36, fg_color=BG, border_color='#E8E7F0',
                         button_color=PINK, button_hover_color='#A91A5E', text_color=INK)


class AssignmentPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent, variables, rows, on_summary=None):
        super().__init__(parent, fg_color='white')
        self.variables = variables
        self.rows = [dict(row) for row in rows]
        self.widgets = {}
        self.edit_index = None
        self.on_summary = on_summary
        self.grid_columnconfigure((0,1,2), weight=1, uniform='assignment')
        for col,(key,caption) in enumerate((('regional','Regional *'),('horas_totales','Horas totales *'),('periodo_horas','Periodo *'))):
            ctk.CTkLabel(self,text=caption,text_color='#77758A').grid(row=0,column=col,sticky='w',padx=8)
            if key=='regional':
                widget=combo(self,variables[key],['',*REGIONAL_OPTIONS],self.region_changed)
            elif key=='periodo_horas':
                widget=combo(self,variables[key],['',*PERIODOS],lambda v:self.refresh_summary())
            else:
                widget=ManagedEntry(self,textvariable=variables[key],height=36)
            widget.grid(row=1,column=col,sticky='ew',padx=8)
            self.widgets[key]=widget
        self.total_trace = variables['horas_totales'].trace_add('write',lambda *a:self.refresh_summary())
        self.summary_labels={}
        for row,key in enumerate(('sede','modalidad'),start=2):
            caption='Sedes' if key=='sede' else 'Modalidades'
            widget=ctk.CTkLabel(self,text='',anchor='w',justify='left',wraplength=800,text_color='#77758A')
            widget.grid(row=row,column=0,columnspan=3,sticky='ew',padx=8,pady=3)
            self.summary_labels[key]=(widget,caption);self.widgets[key]=widget
        ctk.CTkLabel(self,text='Agregar una asignación de sede, modalidad y perfil',font=('Segoe UI',15,'bold')).grid(row=4,column=0,columnspan=3,sticky='w',padx=8,pady=(10,4))
        self.inputs={k:tk.StringVar() for k in ASSIGNMENT_KEYS}
        self.controls={}
        for index,(key,caption) in enumerate((('regional','Regional de esta asignación'),('sede','Sede'),('modalidad','Modalidad'),('perfil','Perfil profesional'),('horas','Horas de esta asignación'))):
            row,col=5+(index//3)*2,index%3
            ctk.CTkLabel(self,text=caption,text_color='#77758A').grid(row=row,column=col,sticky='w',padx=8)
            if key in ('regional','sede','modalidad'):
                values=['',*SEDES] if key=='sede' else ['']
                widget=combo(self,self.inputs[key],values,self.assignment_region_changed if key=='regional' else None)
            elif key=='perfil':
                widget=ctk.CTkComboBox(self,variable=self.inputs[key],values=['Gestor','Psicólogo','Trabajador social','Educador','Auxiliar','Coordinador'],height=36,button_color=PINK)
            else:
                widget=ManagedEntry(self,textvariable=self.inputs[key],height=36)
            widget.grid(row=row+1,column=col,sticky='ew',padx=8)
            self.controls[key]=widget
        self.add_button=ctk.CTkButton(self,text='Añadir asignación',command=self.add,fg_color=PINK,height=36)
        self.add_button.grid(row=8,column=2,sticky='ew',padx=8)
        frame=ctk.CTkFrame(self,fg_color='white')
        frame.grid(row=10,column=0,columnspan=3,sticky='ew',padx=8,pady=(12,0));frame.grid_columnconfigure(0,weight=1)
        self.tree=ttk.Treeview(frame,columns=ASSIGNMENT_KEYS,show='headings',height=4,selectmode='browse',style='Assignments.Treeview')
        for key,width in zip(ASSIGNMENT_KEYS,(125,100,260,170,70)):
            self.tree.heading(key,text=key.capitalize());self.tree.column(key,width=width,minwidth=70,stretch=False)
        self.tree.grid(row=0,column=0,sticky='ew')
        vertical=ctk.CTkScrollbar(frame,command=self.tree.yview);vertical.grid(row=0,column=1,sticky='ns')
        horizontal=ctk.CTkScrollbar(frame,orientation='horizontal',command=self.tree.xview,height=14);horizontal.grid(row=1,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.tree.bind('<Double-1>',lambda e:self.edit())
        actions=ctk.CTkFrame(self,fg_color='transparent');actions.grid(row=11,column=0,columnspan=3,sticky='ew',padx=8,pady=8)
        for caption,callback in [('Editar fila',self.edit),('Quitar fila',self.remove),('Cancelar edición de fila',self.reset_form)]:
            ctk.CTkButton(actions,text=caption,command=callback,fg_color='#6B677D',height=32,width=140).pack(side='left',padx=(0,8))
        self.balance=ctk.CTkLabel(self,text='',anchor='w',text_color=PINK,wraplength=800)
        self.balance.grid(row=9,column=0,columnspan=3,sticky='ew',padx=8,pady=(0,8))
        self.region_changed(variables['regional'].get())
        self.reset_form();self.render()

    def destroy(self):
        self.variables['horas_totales'].trace_remove('write',self.total_trace)
        super().destroy()

    def region_changed(self, value):
        allowed=members(value)
        self.controls['regional'].configure(values=['',*allowed])
        if value == 'Ambas':
            self.inputs['regional'].set('')
        if self.inputs['regional'].get() not in allowed:
            self.inputs['regional'].set(allowed[0] if len(allowed)==1 else '')
        self.assignment_region_changed(self.inputs['regional'].get())
        self.refresh_summary()

    def assignment_region_changed(self,value):
        options=modalities(value or self.variables['regional'].get())
        self.controls['modalidad'].configure(values=['',*options])
        if self.inputs['modalidad'].get() not in options:self.inputs['modalidad'].set('')

    def reset_form(self):
        self.edit_index=None
        for variable in self.inputs.values():variable.set('')
        allowed=members(self.variables['regional'].get())
        if len(allowed)==1:self.inputs['regional'].set(allowed[0])
        self.assignment_region_changed(self.inputs['regional'].get())
        self.add_button.configure(text='Añadir asignación')
        self.form_initial={k:v.get() for k,v in self.inputs.items()}

    def add(self):
        row={k:v.get().strip() for k,v in self.inputs.items()}
        try:
            # Valida la fila sin exigir aquí el reparto global, que puede estar en edición.
            canonical_assignments([row],row['regional'],row['horas'],self.variables['periodo_horas'].get())
            if row['regional'] not in members(self.variables['regional'].get()):
                raise ValueError('Elige una regional que pertenezca al empleado.')
            row['horas']=hours_text(hundredths(row['horas']))
        except ValueError as error:
            messagebox.showwarning('Revisa la asignación',str(error),parent=self.winfo_toplevel());return
        if self.edit_index is None:self.rows.append(row)
        else:self.rows[self.edit_index]=row
        self.reset_form();self.render()

    def edit(self):
        selected=self.tree.selection()
        if not selected:return
        self.edit_index=int(selected[0])
        row=self.rows[self.edit_index]
        self.inputs['regional'].set(row['regional']);self.assignment_region_changed(row['regional'])
        for key in ASSIGNMENT_KEYS:self.inputs[key].set(row[key])
        self.add_button.configure(text='Aplicar cambios de fila')

    def remove(self):
        selected=self.tree.selection()
        if selected:
            self.rows.pop(int(selected[0]));self.reset_form();self.render()

    def render(self):
        self.tree.delete(*self.tree.get_children())
        for i,row in enumerate(self.rows):self.tree.insert('','end',iid=str(i),values=[row[k] for k in ASSIGNMENT_KEYS])
        if self.rows:
            for key in ('sede','modalidad'):self.variables[key].set(summary(self.rows,key))
        self.refresh_summary()

    def refresh_summary(self):
        if not hasattr(self,'balance'):return
        distributed=sum(hundredths(row['horas']) for row in self.rows)
        for key,(widget,caption) in self.summary_labels.items():
            text=summary(self.rows,key) if self.rows else (self.variables[key].get() or 'Sin asignar')
            widget.configure(text=caption+': '+text)
        try:
            total=hundredths(self.variables['horas_totales'].get())
            difference=total-distributed
            state='Completo' if difference==0 else ('Faltan '+hours_text(difference)+' horas' if difference>0 else 'Exceso de '+hours_text(-difference)+' horas')
        except ValueError:
            state='Escribe el total de horas'
        invalid=any(r['regional'] not in members(self.variables['regional'].get()) for r in self.rows)
        if invalid:state+=' · Hay filas de otra regional: revísalas antes de guardar'
        self.balance.configure(text=f"Distribuidas: {hours_text(distributed)} · {self.variables['periodo_horas'].get() or 'Elige periodo'} · {state}")

    def pending_form(self):
        return self.edit_index is not None or {k:v.get() for k,v in self.inputs.items()}!=self.form_initial

    def require_complete(self):
        if self.pending_form():raise ValueError('Pulsa Añadir asignación o Aplicar cambios de fila antes de guardar; también puedes cancelar la edición de la fila.')
        if not self.rows:raise ValueError('Registra al menos una asignación con sede, modalidad, perfil y horas.')
        return canonical_assignments(self.rows,self.variables['regional'].get(),self.variables['horas_totales'].get(),self.variables['periodo_horas'].get())
