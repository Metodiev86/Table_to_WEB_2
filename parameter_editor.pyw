import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

class ParameterEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Редактор на параметри за справки")
        self.root.geometry("900x700")

        # Данни
        self.data = {
            "title": "",
            "category": "",
            "parameters": []
        }
        self.current_param_index = -1
        self.current_option_index = -1

        # Създаване на интерфейс
        self.create_widgets()

    def create_widgets(self):
        # Тулбар за файлови операции
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="Зареди JSON", command=self.load_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Запази JSON", command=self.save_json).pack(side=tk.LEFT, padx=2)

        # Головни полета
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Заглавие на справката:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=60)
        self.title_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Категория:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.category_entry = ttk.Entry(main_frame, width=60)
        self.category_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        # Разделител
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=10)

        # Параметри
        ttk.Label(main_frame, text="Параметри:").grid(row=3, column=0, sticky=tk.W)

        # Списък с параметри
        param_list_frame = ttk.Frame(main_frame)
        param_list_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=5)

        self.param_listbox = tk.Listbox(param_list_frame, height=8)
        self.param_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.param_listbox.bind("<<ListboxSelect>>", self.on_param_select)

        param_scroll = ttk.Scrollbar(param_list_frame, orient=tk.VERTICAL, command=self.param_listbox.yview)
        param_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.param_listbox.config(yscrollcommand=param_scroll.set)

        # Бутон за параметри
        param_btn_frame = ttk.Frame(main_frame)
        param_btn_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)

        ttk.Button(param_btn_frame, text="Добави параметър", command=self.add_param).pack(side=tk.LEFT, padx=2)
        ttk.Button(param_btn_frame, text="Актуализирай параметър", command=self.update_param).pack(side=tk.LEFT, padx=2)
        ttk.Button(param_btn_frame, text="Изтрий параметър", command=self.delete_param).pack(side=tk.LEFT, padx=2)

        # Форма за редактиране на параметър
        param_edit_frame = ttk.LabelFrame(main_frame, text="Редакция на параметър", padding=10)
        param_edit_frame.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=10)

        ttk.Label(param_edit_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.param_name = ttk.Entry(param_edit_frame, width=30)
        self.param_name.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(param_edit_frame, text="Label:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.param_label = ttk.Entry(param_edit_frame, width=30)
        self.param_label.grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(param_edit_frame, text="Type:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.param_type = ttk.Combobox(param_edit_frame, values=["date", "select", "number", "checkbox"], state="readonly", width=27)
        self.param_type.grid(row=2, column=1, sticky=tk.W, pady=2)
        self.param_type.bind("<<ComboboxSelected>>", self.on_param_type_change)

        ttk.Label(param_edit_frame, text="Default:").grid(row=3, column=0, sticky=tk.W, pady=2)
        
        # Контейнер за полето за default, за да можем да сменяме widget
        self.default_container = ttk.Frame(param_edit_frame)
        self.default_container.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        self.param_default_entry = ttk.Entry(self.default_container, width=30)
        self.param_default_combobox = ttk.Combobox(self.default_container, values=["True", "False"], state="readonly", width=27)
        self.current_default_widget = None

        # SQL query за динамично зареждане
        ttk.Label(param_edit_frame, text="SQL Query (динамично):").grid(row=4, column=0, sticky=tk.NW, pady=2)
        self.param_query_text = tk.Text(param_edit_frame, width=60, height=5, wrap=tk.WORD)
        self.param_query_text.grid(row=4, column=1, sticky=tk.EW, pady=2)

        # Опции за select
        self.options_frame = ttk.LabelFrame(param_edit_frame, text="Опции за select (статични)", padding=10)
        self.options_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=10)
        self.options_frame.grid_remove()  # Скриваме по подразбиране

        # Списък с опции
        option_list_frame = ttk.Frame(self.options_frame)
        option_list_frame.pack(fill=tk.BOTH, expand=True)

        self.option_listbox = tk.Listbox(option_list_frame, height=5)
        self.option_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.option_listbox.bind("<<ListboxSelect>>", self.on_option_select)

        option_scroll = ttk.Scrollbar(option_list_frame, orient=tk.VERTICAL, command=self.option_listbox.yview)
        option_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.option_listbox.config(yscrollcommand=option_scroll.set)

        # Бутон за опции
        option_btn_frame = ttk.Frame(self.options_frame)
        option_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(option_btn_frame, text="Добави опция", command=self.add_option).pack(side=tk.LEFT, padx=2)
        ttk.Button(option_btn_frame, text="Актуализирай опция", command=self.update_option).pack(side=tk.LEFT, padx=2)
        ttk.Button(option_btn_frame, text="Изтрий опция", command=self.delete_option).pack(side=tk.LEFT, padx=2)

        # Форма за опция
        option_edit_frame = ttk.Frame(self.options_frame)
        option_edit_frame.pack(fill=tk.X, pady=5)

        ttk.Label(option_edit_frame, text="Value:").pack(side=tk.LEFT, padx=2)
        self.option_value = ttk.Entry(option_edit_frame, width=20)
        self.option_value.pack(side=tk.LEFT, padx=2)

        ttk.Label(option_edit_frame, text="Label:").pack(side=tk.LEFT, padx=2)
        self.option_label = ttk.Entry(option_edit_frame, width=20)
        self.option_label.pack(side=tk.LEFT, padx=2)

        main_frame.columnconfigure(1, weight=1)

    def set_default_widget(self, param_type):
        # Скриваме всички
        if self.current_default_widget:
            self.current_default_widget.pack_forget()
        
        if param_type == "checkbox":
            self.current_default_widget = self.param_default_combobox
        else:
            self.current_default_widget = self.param_default_entry
        
        self.current_default_widget.pack()

    def get_default_value(self):
        if self.current_default_widget == self.param_default_combobox:
            return self.param_default_combobox.get()
        else:
            return self.param_default_entry.get()

    def set_default_value(self, value):
        if self.current_default_widget == self.param_default_combobox:
            self.param_default_combobox.set(str(value))
        else:
            self.param_default_entry.delete(0, tk.END)
            self.param_default_entry.insert(0, str(value) if value is not None else "")

    def load_json(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                self.update_ui()
                messagebox.showinfo("Успех", "Файлът е зареден успешно!")
            except Exception as e:
                messagebox.showerror("Грешка", f"Неуспешно зареждане: {e}")

    def save_json(self):
        # Обновяваме данните от формите
        self.data["title"] = self.title_entry.get()
        self.data["category"] = self.category_entry.get()
        self.save_current_param()  # Запазваме и текущия параметър

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("Успех", "Файлът е запазен успешно!")
            except Exception as e:
                messagebox.showerror("Грешка", f"Неуспешно запазване: {e}")

    def update_ui(self):
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, self.data.get("title", ""))

        self.category_entry.delete(0, tk.END)
        self.category_entry.insert(0, self.data.get("category", ""))

        self.param_listbox.delete(0, tk.END)
        for param in self.data.get("parameters", []):
            self.param_listbox.insert(tk.END, f"{param.get('name', '')} - {param.get('label', '')} ({param.get('type', '')})")

    def save_current_param(self):
        if self.current_param_index < 0 or self.current_param_index >= len(self.data["parameters"]):
            return
        
        param = self.data["parameters"][self.current_param_index]
        param["name"] = self.param_name.get()
        param["label"] = self.param_label.get()
        param["type"] = self.param_type.get()
        
        default_val = self.get_default_value()
        if param["type"] == "number":
            try:
                if default_val and "." in default_val:
                    param["default"] = float(default_val)
                elif default_val:
                    param["default"] = int(default_val)
                else:
                    param["default"] = ""
            except ValueError:
                param["default"] = default_val
        elif param["type"] == "checkbox":
            param["default"] = default_val == "True"
        else:
            param["default"] = default_val

        if param["type"] != "select" and "options" in param:
            del param["options"]

        query_text = self.param_query_text.get("1.0", tk.END).strip()
        if query_text:
            param["query"] = query_text
        else:
            if "query" in param:
                del param["query"]
            if "source" in param:
                del param["source"]

    def on_param_select(self, event):
        # Запазваме текущия параметър преди да заредим нов
        self.save_current_param()
        
        selection = self.param_listbox.curselection()
        if selection:
            self.current_param_index = selection[0]
            param = self.data["parameters"][self.current_param_index]

            self.param_name.delete(0, tk.END)
            self.param_name.insert(0, param.get("name", ""))

            self.param_label.delete(0, tk.END)
            self.param_label.insert(0, param.get("label", ""))

            self.param_type.set(param.get("type", "date"))

            # Сменяме widget за default според типа
            self.set_default_widget(param.get("type", "date"))
            self.set_default_value(param.get("default", ""))

            self.param_query_text.delete("1.0", tk.END)
            existing_query = param.get("query") or (param.get("source") or {}).get("query") or ""
            if existing_query:
                self.param_query_text.insert("1.0", existing_query)

            self.on_param_type_change(None)

            if param.get("type") == "select":
                self.update_options_listbox(param.get("options", []))
        
        # Актуализираме списъка, за да се виждат промените
        self.update_ui()
        if self.current_param_index >= 0 and self.current_param_index < self.param_listbox.size():
            self.param_listbox.selection_set(self.current_param_index)

    def on_param_type_change(self, event):
        # Сменяме widget за default
        self.set_default_widget(self.param_type.get())
        
        if self.param_type.get() == "select":
            self.options_frame.grid()
            if self.current_param_index >= 0:
                param = self.data["parameters"][self.current_param_index]
                self.update_options_listbox(param.get("options", []))
        else:
            self.options_frame.grid_remove()

    def add_param(self):
        new_param = {
            "name": "",
            "label": "",
            "type": "date",
            "default": ""
        }
        self.data["parameters"].append(new_param)
        self.update_ui()
        self.param_listbox.selection_set(tk.END)
        self.on_param_select(None)

    def update_param(self):
        if self.current_param_index < 0:
            messagebox.showwarning("Внимание", "Моля, изберете параметър!")
            return

        self.save_current_param()
        self.update_ui()
        self.param_listbox.selection_set(self.current_param_index)
        messagebox.showinfo("Успех", "Параметърът е актуализиран!")

    def delete_param(self):
        if self.current_param_index < 0:
            messagebox.showwarning("Внимание", "Моля, изберете параметър!")
            return

        del self.data["parameters"][self.current_param_index]
        self.current_param_index = -1
        self.update_ui()
        self.clear_param_form()

    def clear_param_form(self):
        self.param_name.delete(0, tk.END)
        self.param_label.delete(0, tk.END)
        self.param_type.set("")
        self.param_query_text.delete("1.0", tk.END)
        if self.current_default_widget:
            self.current_default_widget.pack_forget()
            self.current_default_widget = None
        self.options_frame.grid_remove()
        self.option_listbox.delete(0, tk.END)

    def update_options_listbox(self, options):
        self.option_listbox.delete(0, tk.END)
        for opt in options:
            self.option_listbox.insert(tk.END, f"{opt.get('value', '')} - {opt.get('label', '')}")

    def on_option_select(self, event):
        selection = self.option_listbox.curselection()
        if selection and self.current_param_index >= 0:
            self.current_option_index = selection[0]
            param = self.data["parameters"][self.current_param_index]
            options = param.get("options", [])
            if self.current_option_index < len(options):
                opt = options[self.current_option_index]
                self.option_value.delete(0, tk.END)
                self.option_value.insert(0, opt.get("value", ""))
                self.option_label.delete(0, tk.END)
                self.option_label.insert(0, opt.get("label", ""))

    def add_option(self):
        if self.current_param_index < 0:
            messagebox.showwarning("Внимание", "Моля, изберете параметър от тип select!")
            return

        param = self.data["parameters"][self.current_param_index]
        if "options" not in param:
            param["options"] = []
        param["options"].append({"value": "", "label": ""})
        self.update_options_listbox(param["options"])
        self.option_listbox.selection_set(tk.END)
        self.on_option_select(None)

    def update_option(self):
        if self.current_param_index < 0 or self.current_option_index < 0:
            messagebox.showwarning("Внимание", "Моля, изберете параметър и опция!")
            return

        param = self.data["parameters"][self.current_param_index]
        options = param.get("options", [])
        if self.current_option_index < len(options):
            options[self.current_option_index]["value"] = self.option_value.get()
            options[self.current_option_index]["label"] = self.option_label.get()
            self.update_options_listbox(options)
            self.option_listbox.selection_set(self.current_option_index)

    def delete_option(self):
        if self.current_param_index < 0 or self.current_option_index < 0:
            messagebox.showwarning("Внимание", "Моля, изберете параметър и опция!")
            return

        param = self.data["parameters"][self.current_param_index]
        options = param.get("options", [])
        if self.current_option_index < len(options):
            del options[self.current_option_index]
            self.current_option_index = -1
            self.update_options_listbox(options)
            self.option_value.delete(0, tk.END)
            self.option_label.delete(0, tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = ParameterEditor(root)
    root.mainloop()
