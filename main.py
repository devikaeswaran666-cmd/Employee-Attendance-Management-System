
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import date

# Database connection
con = sqlite3.connect("employee.db")
cur = con.cursor()

# Create tables
cur.execute("""
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT,
    phone TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(employee_id, attendance_date),
    FOREIGN KEY(employee_id) REFERENCES employees(id)
)
""")

con.commit()

# Main window
root = tk.Tk()
root.title("Employee Attendance Management System")
root.geometry("1000x700")
root.configure(bg="#f0f4f8")

# Heading
tk.Label(
    root,
    text="EMPLOYEE ATTENDANCE AND DETAILS",
    font=("Arial", 20, "bold"),
    bg="#17365d",
    fg="white",
    pady=15
).pack(fill="x")

# Employee form
form = tk.LabelFrame(
    root, text="Employee Details",
    font=("Arial", 12, "bold"),
    bg="#f0f4f8", padx=15, pady=10
)
form.pack(fill="x", padx=15, pady=10)

tk.Label(form, text="Employee ID", bg="#f0f4f8").grid(
    row=0, column=0, padx=10, pady=8, sticky="w"
)
id_entry = tk.Entry(form, width=25)
id_entry.grid(row=0, column=1, padx=10, pady=8)

tk.Label(form, text="Employee Name", bg="#f0f4f8").grid(
    row=0, column=2, padx=10, pady=8, sticky="w"
)
name_entry = tk.Entry(form, width=25)
name_entry.grid(row=0, column=3, padx=10, pady=8)

tk.Label(form, text="Department", bg="#f0f4f8").grid(
    row=1, column=0, padx=10, pady=8, sticky="w"
)
dept_entry = tk.Entry(form, width=25)
dept_entry.grid(row=1, column=1, padx=10, pady=8)

tk.Label(form, text="Phone Number", bg="#f0f4f8").grid(
    row=1, column=2, padx=10, pady=8, sticky="w"
)
phone_entry = tk.Entry(form, width=25)
phone_entry.grid(row=1, column=3, padx=10, pady=8)

# Attendance form
attendance_frame = tk.LabelFrame(
    root, text="Attendance Details",
    font=("Arial", 12, "bold"),
    bg="#f0f4f8", padx=15, pady=10
)
attendance_frame.pack(fill="x", padx=15, pady=5)

tk.Label(attendance_frame, text="Date (YYYY-MM-DD)", bg="#f0f4f8").grid(
    row=0, column=0, padx=10, pady=8
)
date_entry = tk.Entry(attendance_frame, width=20)
date_entry.grid(row=0, column=1, padx=10, pady=8)
date_entry.insert(0, date.today().isoformat())

tk.Label(attendance_frame, text="Status", bg="#f0f4f8").grid(
    row=0, column=2, padx=10, pady=8
)
status_box = ttk.Combobox(
    attendance_frame,
    values=["Present", "Absent", "Leave"],
    state="readonly",
    width=17
)
status_box.grid(row=0, column=3, padx=10, pady=8)
status_box.set("Present")

# Records table
table_frame = tk.LabelFrame(
    root, text="Employee and Attendance Records",
    font=("Arial", 12, "bold"),
    bg="#f0f4f8"
)
table_frame.pack(fill="both", expand=True, padx=15, pady=10)

columns = ("ID", "Name", "Department", "Phone", "Date", "Status")

tree = ttk.Treeview(
    table_frame, columns=columns, show="headings", height=8
)

for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=130, anchor="center")

scrollbar = ttk.Scrollbar(
    table_frame, orient="vertical", command=tree.yview
)
tree.configure(yscrollcommand=scrollbar.set)

tree.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")


# Clear table
def clear_table():
    for item in tree.get_children():
        tree.delete(item)


# Clear form
def clear_fields():
    for entry in (id_entry, name_entry, dept_entry, phone_entry):
        entry.delete(0, tk.END)

    date_entry.delete(0, tk.END)
    date_entry.insert(0, date.today().isoformat())
    status_box.set("Present")


# View all records
def view_all():
    clear_table()

    cur.execute("""
        SELECT e.id, e.name, e.department, e.phone,
               a.attendance_date, a.status
        FROM employees e
        LEFT JOIN attendance a ON e.id = a.employee_id
        ORDER BY e.id, a.attendance_date
    """)

    for row in cur.fetchall():
        tree.insert("", tk.END, values=row)


# Add employee
def add_employee():
    try:
        emp_id = int(id_entry.get())
        name = name_entry.get().strip()

        if emp_id <= 0 or not name:
            messagebox.showwarning(
                "Warning", "Enter a valid ID and employee name"
            )
            return

        cur.execute(
            "INSERT INTO employees VALUES (?, ?, ?, ?)",
            (emp_id, name, dept_entry.get(), phone_entry.get())
        )
        con.commit()

        messagebox.showinfo("Success", "Employee added successfully")
        view_all()

    except ValueError:
        messagebox.showerror("Error", "Employee ID must be a number")
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", "Employee ID already exists")


# Search employee
def search_employee():
    try:
        emp_id = int(id_entry.get())
    except ValueError:
        messagebox.showerror("Error", "Enter a valid Employee ID")
        return

    clear_table()

    cur.execute("""
        SELECT e.id, e.name, e.department, e.phone,
               a.attendance_date, a.status
        FROM employees e
        LEFT JOIN attendance a ON e.id = a.employee_id
        WHERE e.id = ?
        ORDER BY a.attendance_date
    """, (emp_id,))

    rows = cur.fetchall()

    for row in rows:
        tree.insert("", tk.END, values=row)

    if not rows:
        messagebox.showinfo("Search", "Employee not found")


# Update employee
def update_employee():
    try:
        emp_id = int(id_entry.get())
        name = name_entry.get().strip()

        if not name:
            messagebox.showwarning("Warning", "Enter employee name")
            return

        cur.execute("""
            UPDATE employees
            SET name = ?, department = ?, phone = ?
            WHERE id = ?
        """, (name, dept_entry.get(), phone_entry.get(), emp_id))

        con.commit()

        if cur.rowcount == 0:
            messagebox.showerror("Error", "Employee not found")
        else:
            messagebox.showinfo("Success", "Employee updated successfully")
            view_all()

    except ValueError:
        messagebox.showerror("Error", "Enter a valid Employee ID")


# Delete employee
def delete_employee():
    try:
        emp_id = int(id_entry.get())
    except ValueError:
        messagebox.showerror("Error", "Enter a valid Employee ID")
        return

    cur.execute("SELECT id FROM employees WHERE id = ?", (emp_id,))

    if cur.fetchone() is None:
        messagebox.showerror("Error", "Employee not found")
        return

    confirm = messagebox.askyesno(
        "Confirm Delete",
        "Delete employee and all their attendance records?"
    )

    if confirm:
        cur.execute("DELETE FROM attendance WHERE employee_id = ?", (emp_id,))
        cur.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        con.commit()

        messagebox.showinfo("Success", "Employee deleted successfully")
        clear_fields()
        view_all()


# Mark attendance
def mark_attendance():
    try:
        emp_id = int(id_entry.get())
        attendance_date = date_entry.get().strip()
        date.fromisoformat(attendance_date)

        if emp_id <= 0:
            raise ValueError

        status = status_box.get()

        if status not in ["Present", "Absent", "Leave"]:
            messagebox.showwarning("Warning", "Select attendance status")
            return

        cur.execute("SELECT id FROM employees WHERE id = ?", (emp_id,))

        if cur.fetchone() is None:
            messagebox.showerror("Error", "Add employee first")
            return

        cur.execute("""
            INSERT INTO attendance
                (employee_id, attendance_date, status)
            VALUES (?, ?, ?)
            ON CONFLICT(employee_id, attendance_date)
            DO UPDATE SET status = excluded.status
        """, (emp_id, attendance_date, status))

        con.commit()

        messagebox.showinfo("Success", "Attendance saved successfully")
        view_all()

    except ValueError:
        messagebox.showerror(
            "Error", "Enter valid ID and date (YYYY-MM-DD)"
        )


# Attendance summary
def attendance_summary():
    try:
        emp_id = int(id_entry.get())
    except ValueError:
        messagebox.showerror("Error", "Enter a valid Employee ID")
        return

    cur.execute("SELECT name FROM employees WHERE id = ?", (emp_id,))
    employee = cur.fetchone()

    if employee is None:
        messagebox.showerror("Error", "Employee not found")
        return

    cur.execute("""
        SELECT status, COUNT(*)
        FROM attendance
        WHERE employee_id = ?
        GROUP BY status
    """, (emp_id,))

    counts = dict(cur.fetchall())

    summary = (
        "Employee: " + employee[0] + "\n\n"
        + "Present: " + str(counts.get("Present", 0)) + "\n"
        + "Absent: " + str(counts.get("Absent", 0)) + "\n"
        + "Leave: " + str(counts.get("Leave", 0))
    )

    messagebox.showinfo("Attendance Summary", summary)


# Fill form when selecting a table row
def select_employee(event):
    selected = tree.selection()

    if not selected:
        return

    values = tree.item(selected[0], "values")

    clear_fields()

    id_entry.insert(0, values[0])
    name_entry.insert(0, values[1])
    dept_entry.insert(0, values[2] or "")
    phone_entry.insert(0, values[3] or "")

    if values[4]:
        date_entry.delete(0, tk.END)
        date_entry.insert(0, values[4])

    if values[5]:
        status_box.set(values[5])


tree.bind("<<TreeviewSelect>>", select_employee)

# Buttons
buttons = tk.Frame(root, bg="#f0f4f8")
buttons.pack(pady=10)

button_list = [
    ("Add Employee", add_employee),
    ("View All", view_all),
    ("Search Employee", search_employee),
    ("Update Employee", update_employee),
    ("Delete Employee", delete_employee),
    ("Mark Attendance", mark_attendance),
    ("Attendance Summary", attendance_summary),
    ("Clear Fields", clear_fields)
]

for i, (text, command) in enumerate(button_list):
    tk.Button(
        buttons,
        text=text,
        command=command,
        width=18,
        bg="#17365d",
        fg="white",
        padx=5,
        pady=5
    ).grid(row=i // 4, column=i % 4, padx=5, pady=5)


# Close application
def close_app():
    con.close()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", close_app)

# Load existing records
view_all()

root.mainloop()