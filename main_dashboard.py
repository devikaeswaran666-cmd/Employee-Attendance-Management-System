import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
import hashlib
import shutil
import os
from datetime import date, datetime, timedelta

DB_NAME = "employee.db"

# ---------- THEME ----------
BG = "#F3F5FB"
SIDEBAR = "#18243A"
SIDEBAR_HOVER = "#263650"
WHITE = "#FFFFFF"
TEXT = "#202B3C"
MUTED = "#758198"
PURPLE = "#6C63FF"
BLUE = "#3B82F6"
GREEN = "#16A779"
RED = "#EF5261"
ORANGE = "#F59E0B"
TEAL = "#0EA5A4"

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PeoplePulse | Employee Attendance")
        self.root.geometry("1280x800")
        self.root.minsize(1000, 650)
        self.root.configure(bg=BG)
        self.current_admin = None
        self.selected_employee_id = None

        self.setup_database()
        self.setup_styles()
        self.show_login()

    # ---------- DATABASE / SAFE MIGRATION ----------
    def connect(self):
        con = sqlite3.connect(DB_NAME)
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def setup_database(self):
        with self.connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    department TEXT,
                    phone TEXT
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    attendance_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    UNIQUE(employee_id, attendance_date),
                    FOREIGN KEY(employee_id) REFERENCES employees(id)
                )
            """)
            # Add new fields only when missing, keeping existing rows.
            columns = {row[1] for row in con.execute("PRAGMA table_info(attendance)")}
            if "check_in" not in columns:
                con.execute("ALTER TABLE attendance ADD COLUMN check_in TEXT")
            if "check_out" not in columns:
                con.execute("ALTER TABLE attendance ADD COLUMN check_out TEXT")
            if "notes" not in columns:
                con.execute("ALTER TABLE attendance ADD COLUMN notes TEXT")
            con.execute("""
                CREATE TABLE IF NOT EXISTS leave_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(employee_id) REFERENCES employees(id)
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS holidays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    holiday_date TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    notes TEXT
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
            """)
            # Demo credentials: change these after first login.
            count = con.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
            if count == 0:
                con.execute(
                    "INSERT INTO admins(username, password_hash) VALUES (?, ?)",
                    ("admin", hash_password("Admin@123"))
                )

    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", background=WHITE, foreground=TEXT,
                        rowheight=30, fieldbackground=WHITE, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#E9EDFA",
                        foreground=TEXT, font=("Segoe UI", 10, "bold"),
                        relief="flat")
        style.map("Treeview", background=[("selected", "#DDE4FF")],
                  foreground=[("selected", TEXT)])
        style.configure("TCombobox", padding=6)

    # ---------- COMMON UI ----------
    def clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def button(self, parent, text, command, bg=PURPLE, fg=WHITE, **kwargs):
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=bg, activeforeground=fg,
                         relief="flat", bd=0, cursor="hand2",
                         font=("Segoe UI", 10, "bold"), padx=13, pady=9,
                         **kwargs)

    def label(self, parent, text, size=10, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", WHITE),
                        fg=color, font=("Segoe UI", size, "bold" if bold else "normal"),
                        **kwargs)

    def card(self, parent, title, value, color, subtitle="Today"):
        frame = tk.Frame(parent, bg=WHITE, highlightbackground="#E5E9F2",
                         highlightthickness=1)
        tk.Frame(frame, bg=color, width=6).pack(side="left", fill="y")
        inner = tk.Frame(frame, bg=WHITE, padx=16, pady=13)
        inner.pack(side="left", fill="both", expand=True)
        self.label(inner, title, 10, MUTED, True).pack(anchor="w")
        val = self.label(inner, str(value), 25, TEXT, True)
        val.pack(anchor="w", pady=(5, 0))
        self.label(inner, subtitle, 9, MUTED).pack(anchor="w", pady=(2, 0))
        frame.value_label = val
        return frame

    def log_action(self, action, details=""):
        try:
            with self.connect() as con:
                con.execute("INSERT INTO audit_logs(username, action, details) VALUES (?, ?, ?)",
                            (self.current_admin or "system", action, details))
        except sqlite3.Error:
            pass

    def show_login(self):
        self.clear_root()
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True)

        left = tk.Frame(outer, bg=SIDEBAR, width=480)
        left.pack(side="left", fill="both")
        left.pack_propagate(False)
        tk.Label(left, text="✦", bg=SIDEBAR, fg="#9C97FF",
                 font=("Segoe UI", 48, "bold")).pack(anchor="w", padx=54, pady=(110, 5))
        tk.Label(left, text="PeoplePulse", bg=SIDEBAR, fg=WHITE,
                 font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=56)
        tk.Label(left, text="Employee Attendance\n& Workforce Dashboard",
                 bg=SIDEBAR, fg="#C4CDDD", justify="left",
                 font=("Segoe UI", 16)).pack(anchor="w", padx=58, pady=(14, 24))
        tk.Label(left, text="✓  Smart attendance tracking\n✓  Real-time team overview\n✓  Clear, exportable reports",
                 bg=SIDEBAR, fg="#DDE5F3", justify="left",
                 font=("Segoe UI", 12)).pack(anchor="w", padx=58, pady=4)

        right = tk.Frame(outer, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        login = tk.Frame(right, bg=WHITE, padx=42, pady=38,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        login.place(relx=0.5, rely=0.5, anchor="center", width=410, height=430)
        tk.Label(login, text="Welcome back", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 23, "bold")).pack(anchor="w")
        tk.Label(login, text="Sign in to manage your workforce.",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 24))

        tk.Label(login, text="USERNAME", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.username_entry = tk.Entry(login, font=("Segoe UI", 12), relief="solid",
                                       bd=1, bg="#FBFCFF")
        self.username_entry.pack(fill="x", ipady=9, pady=(7, 17))
        tk.Label(login, text="PASSWORD", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.password_entry = tk.Entry(login, show="•", font=("Segoe UI", 12),
                                       relief="solid", bd=1, bg="#FBFCFF")
        self.password_entry.pack(fill="x", ipady=9, pady=(7, 22))
        self.password_entry.bind("<Return>", lambda _event: self.login())
        self.button(login, "SIGN IN  →", self.login, bg=PURPLE).pack(fill="x")
        tk.Label(login, text="First-time demo: admin  /  Admin@123",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(18, 0))
        self.username_entry.focus_set()

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        with self.connect() as con:
            row = con.execute(
                "SELECT username FROM admins WHERE username=? AND password_hash=?",
                (username, hash_password(password))
            ).fetchone()
        if row:
            self.current_admin = row[0]
            self.show_dashboard()
        else:
            messagebox.showerror("Login failed", "Incorrect username or password.")

    def logout(self):
        if messagebox.askyesno("Log out", "Are you sure you want to log out?"):
            self.current_admin = None
            self.show_login()

    def show_dashboard(self):
        self.clear_root()
        self.root.configure(bg=BG)
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)

        side = tk.Frame(shell, bg=SIDEBAR, width=225)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="✦ PeoplePulse", bg=SIDEBAR, fg=WHITE,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=22, pady=(28, 32))
        navs = [
            ("▦   Dashboard", self.page_dashboard),
            ("♙   Employees", self.page_employees),
            ("◷   Attendance", self.page_attendance),
            ("％   Attendance % Tracking", self.page_percentage),
            ("♧   Leave Management", self.page_leaves),
            ("▦   Holiday Calendar", self.page_holidays),
            ("◈   Team Analytics", self.page_analytics),
            ("▤   Reports & Export", self.page_reports),
            ("⚙   Admin Settings", self.page_admin),
        ]
        for text, cmd in navs:
            b = tk.Button(side, text=text, command=cmd, anchor="w",
                          bg=SIDEBAR, fg="#D8E0EF", activebackground=SIDEBAR_HOVER,
                          activeforeground=WHITE, relief="flat", bd=0, cursor="hand2",
                          font=("Segoe UI", 10, "bold"), padx=22, pady=13)
            b.pack(fill="x", padx=9, pady=2)
        tk.Frame(side, bg="#334158", height=1).pack(fill="x", padx=18, pady=(28, 15))
        tk.Label(side, text=f"Signed in as\n{self.current_admin}",
                 bg=SIDEBAR, fg="#D8E0EF", justify="left",
                 font=("Segoe UI", 10)).pack(anchor="w", padx=22, pady=(0, 14))
        self.button(side, "↪  Log out", self.logout, bg="#34445F").pack(fill="x", padx=15)

        main = tk.Frame(shell, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(main, bg=WHITE, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Employee Management Workspace", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=26)
        tk.Label(header, text=datetime.now().strftime("%A, %d %B %Y"),
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 10)).pack(side="right", padx=25)
        self.content = tk.Frame(main, bg=BG, padx=25, pady=22)
        self.content.pack(fill="both", expand=True)
        self.page_dashboard()

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def page_heading(self, title, subtitle):
        row = tk.Frame(self.content, bg=BG)
        row.pack(fill="x", pady=(0, 20))
        tk.Label(row, text=title, bg=BG, fg=TEXT,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(row, text=subtitle, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))

    # ---------- DASHBOARD ----------
    def page_dashboard(self):
        self.clear_content()
        self.page_heading("Dashboard overview", "A live snapshot of your team's attendance.")
        today = date.today().isoformat()
        with self.connect() as con:
            total = con.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
            present = con.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date=? AND status='Present'", (today,)).fetchone()[0]
            absent = con.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date=? AND status='Absent'", (today,)).fetchone()[0]
            leave = con.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date=? AND status='On Leave'", (today,)).fetchone()[0]
            recent = con.execute("""
                SELECT e.id, e.name, e.department, a.status, a.check_in, a.check_out
                FROM attendance a JOIN employees e ON e.id=a.employee_id
                WHERE a.attendance_date=? ORDER BY e.name LIMIT 8
            """, (today,)).fetchall()
            month = date.today().strftime("%Y-%m")
            month_present = con.execute(
                "SELECT COUNT(*) FROM attendance WHERE attendance_date LIKE ? AND status='Present'",
                (month + "%",)
            ).fetchone()[0]
            month_absent = con.execute(
                "SELECT COUNT(*) FROM attendance WHERE attendance_date LIKE ? AND status='Absent'",
                (month + "%",)
            ).fetchone()[0]
            month_denominator = month_present + month_absent
            month_rate = (month_present / month_denominator * 100) if month_denominator else 0

        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill="x")
        card_data = [
            ("TOTAL EMPLOYEES", total, PURPLE, "Registered team members"),
            ("PRESENT TODAY", present, GREEN, "Marked present"),
            ("ABSENT TODAY", absent, RED, "Marked absent"),
            ("ON LEAVE", leave, ORANGE, "Approved / recorded leave"),
            ("MONTHLY ATTENDANCE", f"{month_rate:.1f}%", TEAL, "Present ÷ (Present + Absent)"),
        ]
        for i, data in enumerate(card_data):
            c = self.card(cards, *data)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0), pady=3)
            cards.grid_columnconfigure(i, weight=1, uniform="cards")

        lower = tk.Frame(self.content, bg=BG)
        lower.pack(fill="both", expand=True, pady=(22, 0))
        left = tk.Frame(lower, bg=WHITE, padx=18, pady=17,
                        highlightbackground="#E5E9F2", highlightthickness=1)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="Today's attendance", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(left, text=today, bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 12))
        cols = ("id", "name", "department", "status", "checkin", "checkout")
        tree = ttk.Treeview(left, columns=cols, show="headings", height=10)
        headings = {"id":"ID", "name":"Employee", "department":"Department",
                    "status":"Status", "checkin":"Check-in", "checkout":"Check-out"}
        widths = {"id":45, "name":160, "department":125, "status":90,
                  "checkin":85, "checkout":85}
        for col in cols:
            tree.heading(col, text=headings[col])
            tree.column(col, width=widths[col], anchor="w")
        for row in recent:
            tree.insert("", "end", values=(row[0], row[1], row[2] or "—",
                                           row[3], row[4] or "—", row[5] or "—"))
        tree.pack(fill="both", expand=True)
        right = tk.Frame(lower, bg=WHITE, width=235, padx=18, pady=17,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        right.pack(side="right", fill="y", padx=(18, 0))
        right.pack_propagate(False)
        tk.Label(right, text="Quick actions", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 12))
        self.button(right, "+ Add employee", self.page_employees, bg=PURPLE).pack(fill="x", pady=5)
        self.button(right, "✓ Mark attendance", self.page_attendance, bg=GREEN).pack(fill="x", pady=5)
        self.button(right, "▤ Export report", self.page_reports, bg=BLUE).pack(fill="x", pady=5)
        self.button(right, "↻ Refresh dashboard", self.page_dashboard, bg="#E9EDFA", fg=TEXT).pack(fill="x", pady=5)
        tk.Label(right, text="Tip: select an employee in the Attendance page to record check-in and check-out times.",
                 bg=WHITE, fg=MUTED, wraplength=190, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(22, 0))

    # ---------- EMPLOYEES ----------
    def page_employees(self):
        self.clear_content()
        self.page_heading("Employee directory", "Create and maintain employee records.")
        panel = tk.Frame(self.content, bg=WHITE, padx=18, pady=16,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        panel.pack(fill="x", pady=(0, 16))
        self.employee_vars = {}
        fields = [("name", "Full name"), ("department", "Department"), ("phone", "Phone")]
        for i, (key, title) in enumerate(fields):
            tk.Label(panel, text=title, bg=WHITE, fg=MUTED,
                     font=("Segoe UI", 9, "bold")).grid(row=0, column=i, sticky="w", padx=(0, 12))
            ent = tk.Entry(panel, font=("Segoe UI", 11), relief="solid", bd=1, bg="#FBFCFF")
            ent.grid(row=1, column=i, sticky="ew", padx=(0, 12), pady=(6, 12), ipady=7)
            self.employee_vars[key] = ent
            panel.grid_columnconfigure(i, weight=1)
        actions = tk.Frame(panel, bg=WHITE)
        actions.grid(row=2, column=0, columnspan=3, sticky="w")
        self.button(actions, "Add employee", self.add_employee, bg=PURPLE).pack(side="left", padx=(0, 7))
        self.button(actions, "Update selected", self.update_employee, bg=BLUE).pack(side="left", padx=7)
        self.button(actions, "Delete selected", self.delete_employee, bg=RED).pack(side="left", padx=7)
        self.button(actions, "Clear", self.clear_employee_form, bg="#E9EDFA", fg=TEXT).pack(side="left", padx=7)

        searchrow = tk.Frame(self.content, bg=BG)
        searchrow.pack(fill="x", pady=(0, 10))
        tk.Label(searchrow, text="Search by name / department / phone", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self.emp_search = tk.Entry(searchrow, font=("Segoe UI", 10), width=28, relief="solid", bd=1)
        self.emp_search.pack(side="left", padx=10, ipady=5)
        self.button(searchrow, "Search", self.load_employees, bg=BLUE, pady=6).pack(side="left")
        self.button(searchrow, "Show all", lambda: (self.emp_search.delete(0, "end"), self.load_employees()), bg="#E9EDFA", fg=TEXT, pady=6).pack(side="left", padx=7)

        cols = ("id", "name", "department", "phone")
        self.emp_tree = ttk.Treeview(self.content, columns=cols, show="headings", height=11)
        for col, title, width in [("id","ID",70), ("name","Full name",280), ("department","Department",220), ("phone","Phone",200)]:
            self.emp_tree.heading(col, text=title)
            self.emp_tree.column(col, width=width, anchor="w")
        self.emp_tree.pack(fill="both", expand=True)
        self.emp_tree.bind("<<TreeviewSelect>>", self.on_employee_select)
        self.load_employees()

    def load_employees(self):
        if not hasattr(self, "emp_tree") or not self.emp_tree.winfo_exists():
            return
        for item in self.emp_tree.get_children():
            self.emp_tree.delete(item)
        search = self.emp_search.get().strip() if hasattr(self, "emp_search") else ""
        with self.connect() as con:
            if search:
                rows = con.execute("""
                    SELECT id, name, department, phone FROM employees
                    WHERE name LIKE ? OR department LIKE ? OR phone LIKE ?
                    ORDER BY id DESC
                """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
            else:
                rows = con.execute("SELECT id, name, department, phone FROM employees ORDER BY id DESC").fetchall()
        for row in rows:
            self.emp_tree.insert("", "end", values=tuple(x or "" for x in row))

    def clear_employee_form(self):
        self.selected_employee_id = None
        for ent in self.employee_vars.values():
            ent.delete(0, "end")
        if hasattr(self, "emp_tree"):
            for item in self.emp_tree.selection():
                self.emp_tree.selection_remove(item)

    def on_employee_select(self, _event=None):
        selected = self.emp_tree.selection()
        if not selected:
            return
        vals = self.emp_tree.item(selected[0], "values")
        self.selected_employee_id = int(vals[0])
        for key, value in zip(("name", "department", "phone"), vals[1:]):
            self.employee_vars[key].delete(0, "end")
            self.employee_vars[key].insert(0, value)

    def add_employee(self):
        name = self.employee_vars["name"].get().strip()
        dept = self.employee_vars["department"].get().strip()
        phone = self.employee_vars["phone"].get().strip()
        if not name:
            messagebox.showwarning("Required field", "Please enter the employee's name.")
            return
        try:
            with self.connect() as con:
                con.execute("INSERT INTO employees(name, department, phone) VALUES (?, ?, ?)",
                            (name, dept, phone))
            messagebox.showinfo("Success", "Employee added successfully.")
            self.clear_employee_form()
            self.load_employees()
        except sqlite3.Error as exc:
            messagebox.showerror("Database error", str(exc))

    def update_employee(self):
        if not self.selected_employee_id:
            messagebox.showwarning("Select employee", "Choose an employee from the table first.")
            return
        name = self.employee_vars["name"].get().strip()
        if not name:
            messagebox.showwarning("Required field", "Name cannot be empty.")
            return
        with self.connect() as con:
            con.execute("UPDATE employees SET name=?, department=?, phone=? WHERE id=?",
                        (name, self.employee_vars["department"].get().strip(),
                         self.employee_vars["phone"].get().strip(), self.selected_employee_id))
        messagebox.showinfo("Updated", "Employee details updated.")
        self.load_employees()

    def delete_employee(self):
        if not self.selected_employee_id:
            messagebox.showwarning("Select employee", "Choose an employee from the table first.")
            return
        if not messagebox.askyesno("Confirm delete", "Delete this employee and their attendance records?"):
            return
        with self.connect() as con:
            con.execute("DELETE FROM attendance WHERE employee_id=?", (self.selected_employee_id,))
            con.execute("DELETE FROM employees WHERE id=?", (self.selected_employee_id,))
        self.clear_employee_form()
        self.load_employees()
        messagebox.showinfo("Deleted", "Employee and related attendance records deleted.")

    # ---------- ATTENDANCE ----------
    def page_attendance(self):
        self.clear_content()
        self.page_heading("Attendance control", "Mark daily status and record working hours.")
        panel = tk.Frame(self.content, bg=WHITE, padx=20, pady=18,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        panel.pack(fill="x", pady=(0, 16))
        with self.connect() as con:
            employees = con.execute("SELECT id, name FROM employees ORDER BY name").fetchall()
        self.att_employee_map = {f"{r[0]} — {r[1]}": r[0] for r in employees}
        tk.Label(panel, text="Employee", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.att_employee = ttk.Combobox(panel, values=list(self.att_employee_map.keys()),
                                          state="readonly", width=32, font=("Segoe UI", 10))
        self.att_employee.grid(row=1, column=0, padx=(0, 15), pady=(6, 14), sticky="ew")
        tk.Label(panel, text="Date (YYYY-MM-DD)", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w")
        self.att_date = tk.Entry(panel, font=("Segoe UI", 10), relief="solid", bd=1)
        self.att_date.insert(0, date.today().isoformat())
        self.att_date.grid(row=1, column=1, padx=(0, 15), pady=(6, 14), ipady=6, sticky="ew")
        tk.Label(panel, text="Status", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w")
        self.att_status = ttk.Combobox(panel, values=["Present", "Absent", "On Leave"],
                                       state="readonly", width=15, font=("Segoe UI", 10))
        self.att_status.set("Present")
        self.att_status.grid(row=1, column=2, padx=(0, 15), pady=(6, 14), ipady=3, sticky="ew")
        for i in range(3):
            panel.grid_columnconfigure(i, weight=1)
        buttons = tk.Frame(panel, bg=WHITE)
        buttons.grid(row=2, column=0, columnspan=3, sticky="w")
        self.button(buttons, "Save attendance", self.save_attendance, bg=PURPLE).pack(side="left", padx=(0, 7))
        self.button(buttons, "Check in now", self.check_in, bg=GREEN).pack(side="left", padx=7)
        self.button(buttons, "Check out now", self.check_out, bg=ORANGE).pack(side="left", padx=7)
        self.button(buttons, "Refresh", self.load_attendance, bg="#E9EDFA", fg=TEXT).pack(side="left", padx=7)

        tk.Label(self.content, text="Attendance records", bg=BG, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 9))
        cols = ("id", "name", "date", "status", "in", "out", "hours")
        self.att_tree = ttk.Treeview(self.content, columns=cols, show="headings", height=11)
        for col, title, width in [
            ("id","ID",55), ("name","Employee",200), ("date","Date",120),
            ("status","Status",100), ("in","Check-in",100), ("out","Check-out",100),
            ("hours","Hours",90)
        ]:
            self.att_tree.heading(col, text=title)
            self.att_tree.column(col, width=width, anchor="w")
        self.att_tree.pack(fill="both", expand=True)
        self.load_attendance()

    def selected_attendance_employee(self):
        key = self.att_employee.get()
        return self.att_employee_map.get(key)

    def valid_attendance_inputs(self):
        emp_id = self.selected_attendance_employee()
        d = self.att_date.get().strip()
        status = self.att_status.get().strip()
        if not emp_id:
            messagebox.showwarning("Select employee", "Please select an employee.")
            return None
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Invalid date", "Use date format YYYY-MM-DD.")
            return None
        if status not in ("Present", "Absent", "On Leave"):
            messagebox.showwarning("Status required", "Choose an attendance status.")
            return None
        return emp_id, d, status

    def save_attendance(self):
        data = self.valid_attendance_inputs()
        if not data:
            return
        emp_id, d, status = data
        with self.connect() as con:
            con.execute("""
                INSERT INTO attendance(employee_id, attendance_date, status)
                VALUES (?, ?, ?)
                ON CONFLICT(employee_id, attendance_date)
                DO UPDATE SET status=excluded.status
            """, (emp_id, d, status))
        self.load_attendance()
        self.log_action("Save attendance", f"Employee ID {emp_id}, {d}: {status}")
        messagebox.showinfo("Saved", f"Attendance saved as {status}.")

    def ensure_attendance_row(self, emp_id, d):
        with self.connect() as con:
            con.execute("""
                INSERT INTO attendance(employee_id, attendance_date, status)
                VALUES (?, ?, 'Present')
                ON CONFLICT(employee_id, attendance_date) DO NOTHING
            """, (emp_id, d))

    def check_in(self):
        emp_id = self.selected_attendance_employee()
        d = self.att_date.get().strip()
        if not emp_id:
            messagebox.showwarning("Select employee", "Please select an employee.")
            return
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Invalid date", "Use date format YYYY-MM-DD.")
            return
        now = datetime.now().strftime("%H:%M:%S")
        self.ensure_attendance_row(emp_id, d)
        with self.connect() as con:
            row = con.execute("SELECT status, check_in FROM attendance WHERE employee_id=? AND attendance_date=?",
                              (emp_id, d)).fetchone()
            if row and row[0] != "Present":
                con.execute("UPDATE attendance SET status='Present' WHERE employee_id=? AND attendance_date=?",
                            (emp_id, d))
            if row and row[1]:
                messagebox.showinfo("Already checked in", f"Check-in already recorded at {row[1]}.")
                return
            con.execute("UPDATE attendance SET check_in=? WHERE employee_id=? AND attendance_date=?",
                        (now, emp_id, d))
        self.load_attendance()
        messagebox.showinfo("Check-in recorded", f"Check-in: {now}")

    def check_out(self):
        emp_id = self.selected_attendance_employee()
        d = self.att_date.get().strip()
        if not emp_id:
            messagebox.showwarning("Select employee", "Please select an employee.")
            return
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Invalid date", "Use date format YYYY-MM-DD.")
            return
        with self.connect() as con:
            row = con.execute("SELECT check_in, check_out FROM attendance WHERE employee_id=? AND attendance_date=?",
                              (emp_id, d)).fetchone()
            if not row or not row[0]:
                messagebox.showwarning("Check-in required", "Record check-in before check-out.")
                return
            if row[1]:
                messagebox.showinfo("Already checked out", f"Check-out already recorded at {row[1]}.")
                return
            now = datetime.now().strftime("%H:%M:%S")
            con.execute("UPDATE attendance SET check_out=? WHERE employee_id=? AND attendance_date=?",
                        (now, emp_id, d))
        self.load_attendance()
        messagebox.showinfo("Check-out recorded", f"Check-out: {now}")

    @staticmethod
    def hours_between(start, end):
        if not start or not end:
            return "—"
        try:
            a = datetime.strptime(start, "%H:%M:%S")
            b = datetime.strptime(end, "%H:%M:%S")
            seconds = int((b-a).total_seconds())
            if seconds < 0:
                seconds += 24 * 3600
            return f"{seconds // 3600}h {seconds % 3600 // 60}m"
        except ValueError:
            return "—"

    def load_attendance(self):
        if not hasattr(self, "att_tree") or not self.att_tree.winfo_exists():
            return
        for item in self.att_tree.get_children():
            self.att_tree.delete(item)
        with self.connect() as con:
            rows = con.execute("""
                SELECT a.id, e.name, a.attendance_date, a.status, a.check_in, a.check_out
                FROM attendance a JOIN employees e ON e.id=a.employee_id
                ORDER BY a.attendance_date DESC, e.name LIMIT 500
            """).fetchall()
        for row in rows:
            self.att_tree.insert("", "end", values=(
                row[0], row[1], row[2], row[3], row[4] or "—", row[5] or "—",
                self.hours_between(row[4], row[5])
            ))

    # ---------- ATTENDANCE PERCENTAGE TRACKING ----------
    def page_percentage(self):
        self.clear_content()
        month = date.today().strftime("%Y-%m")
        self.page_heading(
            "Attendance percentage tracker",
            "Compare employee attendance, spot low attendance, and celebrate top performers."
        )

        controls = tk.Frame(self.content, bg=WHITE, padx=18, pady=14,
                            highlightbackground="#E5E9F2", highlightthickness=1)
        controls.pack(fill="x", pady=(0, 14))
        tk.Label(controls, text="Month (YYYY-MM)", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self.percentage_month = tk.Entry(
            controls, font=("Segoe UI", 11), relief="solid", bd=1, width=12
        )
        self.percentage_month.insert(0, month)
        self.percentage_month.pack(side="left", padx=(10, 12), ipady=5)
        self.button(
            controls, "Calculate percentage",
            self.load_percentage_report, bg=PURPLE, pady=6
        ).pack(side="left")
        self.button(
            controls, "Current month",
            lambda: self.set_percentage_current_month(), bg="#E9EDFA",
            fg=TEXT, pady=6
        ).pack(side="left", padx=8)

        self.percentage_summary = tk.Frame(self.content, bg=BG)
        self.percentage_summary.pack(fill="x", pady=(0, 14))

        body = tk.Frame(self.content, bg=BG)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=WHITE, padx=14, pady=14,
                        highlightbackground="#E5E9F2", highlightthickness=1)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="Employee attendance breakdown", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 8))

        columns = ("name", "department", "present", "absent", "leave", "rate", "progress")
        self.percentage_tree = ttk.Treeview(
            left, columns=columns, show="headings", height=12
        )
        headers = {
            "name": ("Employee", 150), "department": ("Department", 115),
            "present": ("Present", 65), "absent": ("Absent", 65),
            "leave": ("Leave", 60), "rate": ("Attendance %", 100),
            "progress": ("Progress", 130)
        }
        for col in columns:
            title, width = headers[col]
            self.percentage_tree.heading(col, text=title)
            self.percentage_tree.column(col, width=width, minwidth=45, anchor="w")
        self.percentage_tree.tag_configure("high", foreground="#087F5B")
        self.percentage_tree.tag_configure("medium", foreground="#B7791F")
        self.percentage_tree.tag_configure("low", foreground="#C53030")
        self.percentage_tree.pack(fill="both", expand=True)

        right = tk.Frame(body, bg=WHITE, width=235, padx=16, pady=15,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        right.pack(side="right", fill="y", padx=(14, 0))
        right.pack_propagate(False)
        tk.Label(right, text="Insights", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        self.percentage_insights = tk.Frame(right, bg=WHITE)
        self.percentage_insights.pack(fill="both", expand=True, anchor="n", pady=(10, 0))

        self.load_percentage_report()

    def set_percentage_current_month(self):
        if hasattr(self, "percentage_month") and self.percentage_month.winfo_exists():
            self.percentage_month.delete(0, "end")
            self.percentage_month.insert(0, date.today().strftime("%Y-%m"))
            self.load_percentage_report()

    def load_percentage_report(self):
        if not hasattr(self, "percentage_tree") or not self.percentage_tree.winfo_exists():
            return
        month = self.percentage_month.get().strip()
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            messagebox.showwarning("Invalid month", "Enter the month in YYYY-MM format, for example 2026-10.")
            return

        for item in self.percentage_tree.get_children():
            self.percentage_tree.delete(item)
        for widget in self.percentage_summary.winfo_children():
            widget.destroy()
        for widget in self.percentage_insights.winfo_children():
            widget.destroy()

        with self.connect() as con:
            employees = con.execute(
                "SELECT id, name, department FROM employees ORDER BY name"
            ).fetchall()
            records = con.execute("""
                SELECT employee_id,
                       SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN status='On Leave' THEN 1 ELSE 0 END)
                FROM attendance
                WHERE attendance_date LIKE ?
                GROUP BY employee_id
            """, (month + "%",)).fetchall()

        stats = {row[0]: (row[1] or 0, row[2] or 0, row[3] or 0) for row in records}
        report_rows = []
        for emp_id, name, department in employees:
            present, absent, leave = stats.get(emp_id, (0, 0, 0))
            denominator = present + absent  # Leave is excluded from the attendance-rate denominator.
            rate = (present / denominator * 100) if denominator else 0.0
            blocks = round(rate / 10)
            progress = ("█" * blocks) + ("░" * (10 - blocks))
            report_rows.append({
                "id": emp_id, "name": name, "department": department or "—",
                "present": present, "absent": absent, "leave": leave,
                "rate": rate, "progress": progress, "denominator": denominator
            })

        for row in sorted(report_rows, key=lambda x: (-x["rate"], x["name"])):
            if row["denominator"] == 0:
                tag = "medium"
                rate_text = "No data"
                progress = "░░░░░░░░░░"
            else:
                tag = "high" if row["rate"] >= 90 else ("medium" if row["rate"] >= 75 else "low")
                rate_text = f'{row["rate"]:.1f}%'
                progress = row["progress"]
            self.percentage_tree.insert(
                "", "end",
                values=(row["name"], row["department"], row["present"],
                        row["absent"], row["leave"], rate_text, progress),
                tags=(tag,)
            )

        present_total = sum(r["present"] for r in report_rows)
        absent_total = sum(r["absent"] for r in report_rows)
        leave_total = sum(r["leave"] for r in report_rows)
        denominator = present_total + absent_total
        overall_rate = (present_total / denominator * 100) if denominator else 0.0
        recorded_employees = sum(1 for r in report_rows if r["denominator"] > 0)
        low_count = sum(1 for r in report_rows if 0 < r["rate"] < 75 and r["denominator"] > 0)
        top = next((r for r in sorted(report_rows, key=lambda x: (-x["rate"], x["name"]))
                    if r["denominator"] > 0), None)

        cards = [
            ("TEAM ATTENDANCE", f"{overall_rate:.1f}%", PURPLE,
             "Present ÷ (Present + Absent)"),
            ("PRESENT DAYS", present_total, GREEN, f"During {month}"),
            ("ABSENT DAYS", absent_total, RED, "Recorded absences"),
            ("LOW ATTENDANCE", low_count, ORANGE, "Below 75%")
        ]
        for i, (title, value, color, subtitle) in enumerate(cards):
            c = self.card(self.percentage_summary, title, value, color, subtitle)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0))
            self.percentage_summary.grid_columnconfigure(i, weight=1, uniform="pctcards")

        tk.Label(self.percentage_insights,
                 text=f"📅 Report month\n{month}",
                 bg=WHITE, fg=TEXT, font=("Segoe UI", 10, "bold"),
                 justify="left").pack(anchor="w", pady=(0, 14))
        tk.Label(self.percentage_insights,
                 text=f"👥 Employees with records\n{recorded_employees} / {len(employees)}",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 10), justify="left",
                 wraplength=200).pack(anchor="w", pady=(0, 14))
        if top:
            tk.Label(self.percentage_insights, text="🏆 Top attendance",
                     bg=WHITE, fg=GREEN, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(self.percentage_insights,
                     text=f'{top["name"]}\n{top["rate"]:.1f}% attendance',
                     bg=WHITE, fg=TEXT, font=("Segoe UI", 10),
                     justify="left", wraplength=200).pack(anchor="w", pady=(4, 14))
        else:
            tk.Label(self.percentage_insights, text="No attendance records for this month yet.",
                     bg=WHITE, fg=MUTED, font=("Segoe UI", 10),
                     wraplength=200, justify="left").pack(anchor="w", pady=(0, 14))

        tk.Label(self.percentage_insights, text="Status guide",
                 bg=WHITE, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        for label, color in [
            ("90–100%  Excellent", GREEN), ("75–89.9%  Needs focus", ORANGE),
            ("Below 75%  Attention", RED), ("No records  Not rated", MUTED)
        ]:
            tk.Label(self.percentage_insights, text=label, bg=WHITE, fg=color,
                     font=("Segoe UI", 9, "bold"), wraplength=200,
                     justify="left").pack(anchor="w", pady=(5, 0))

    # ---------- LEAVE MANAGEMENT ----------
    def page_leaves(self):
        self.clear_content()
        self.page_heading("Leave management", "Create requests, approve or reject them, and automatically mark approved dates as On Leave.")
        with self.connect() as con:
            employees = con.execute("SELECT id, name FROM employees ORDER BY name").fetchall()
            pending = con.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'").fetchone()[0]
        self.leave_employee_map = {f"{row[0]} — {row[1]}": row[0] for row in employees}
        panel = tk.Frame(self.content, bg=WHITE, padx=18, pady=16,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        panel.pack(fill="x", pady=(0, 14))
        tk.Label(panel, text="Employee", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.leave_employee = ttk.Combobox(panel, values=list(self.leave_employee_map), state="readonly", width=28)
        self.leave_employee.grid(row=1, column=0, padx=(0, 12), pady=(5, 10), sticky="ew")
        tk.Label(panel, text="Start date (YYYY-MM-DD)", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w")
        self.leave_start = tk.Entry(panel, font=("Segoe UI", 10), relief="solid", bd=1)
        self.leave_start.insert(0, date.today().isoformat())
        self.leave_start.grid(row=1, column=1, padx=(0, 12), pady=(5, 10), ipady=5, sticky="ew")
        tk.Label(panel, text="End date (YYYY-MM-DD)", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w")
        self.leave_end = tk.Entry(panel, font=("Segoe UI", 10), relief="solid", bd=1)
        self.leave_end.insert(0, date.today().isoformat())
        self.leave_end.grid(row=1, column=2, padx=(0, 12), pady=(5, 10), ipady=5, sticky="ew")
        tk.Label(panel, text="Reason", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w")
        self.leave_reason = tk.Entry(panel, font=("Segoe UI", 10), relief="solid", bd=1)
        self.leave_reason.grid(row=1, column=3, pady=(5, 10), ipady=5, sticky="ew")
        for i in range(4): panel.grid_columnconfigure(i, weight=1)
        actions = tk.Frame(panel, bg=WHITE); actions.grid(row=2, column=0, columnspan=4, sticky="w")
        self.button(actions, "＋ Add request", self.add_leave_request, bg=PURPLE).pack(side="left", padx=(0, 8))
        self.button(actions, "✓ Approve selected", lambda: self.update_leave_request("Approved"), bg=GREEN).pack(side="left", padx=8)
        self.button(actions, "✕ Reject selected", lambda: self.update_leave_request("Rejected"), bg=RED).pack(side="left", padx=8)
        self.button(actions, "Refresh", self.page_leaves, bg="#E9EDFA", fg=TEXT).pack(side="left", padx=8)
        tk.Label(self.content, text=f"Pending requests: {pending}", bg=BG, fg=ORANGE, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
        cols = ("id", "employee", "start", "end", "reason", "status", "created")
        self.leave_tree = ttk.Treeview(self.content, columns=cols, show="headings", height=13)
        for col, title, width in [("id","ID",45),("employee","Employee",160),("start","Start",105),("end","End",105),("reason","Reason",230),("status","Status",100),("created","Created",145)]:
            self.leave_tree.heading(col, text=title); self.leave_tree.column(col, width=width, anchor="w")
        self.leave_tree.pack(fill="both", expand=True)
        with self.connect() as con:
            rows = con.execute("""SELECT l.id,e.name,l.start_date,l.end_date,l.reason,l.status,l.created_at
                FROM leave_requests l JOIN employees e ON e.id=l.employee_id ORDER BY l.id DESC LIMIT 500""").fetchall()
        for row in rows: self.leave_tree.insert("", "end", values=tuple(x or "—" for x in row))

    def add_leave_request(self):
        emp_id = self.leave_employee_map.get(self.leave_employee.get())
        start, end = self.leave_start.get().strip(), self.leave_end.get().strip()
        reason = self.leave_reason.get().strip()
        if not emp_id:
            messagebox.showwarning("Select employee", "Choose an employee first."); return
        try:
            start_d = datetime.strptime(start, "%Y-%m-%d").date()
            end_d = datetime.strptime(end, "%Y-%m-%d").date()
            if end_d < start_d: raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid dates", "Use YYYY-MM-DD and ensure end date is not before start date."); return
        with self.connect() as con:
            con.execute("INSERT INTO leave_requests(employee_id,start_date,end_date,reason,status) VALUES(?,?,?,?, 'Pending')",
                        (emp_id, start, end, reason))
        self.log_action("Create leave request", f"Employee ID {emp_id}: {start} to {end}")
        self.page_leaves()

    def update_leave_request(self, new_status):
        selected = self.leave_tree.selection() if hasattr(self, "leave_tree") else ()
        if not selected:
            messagebox.showwarning("Select request", "Select a leave request from the table."); return
        values = self.leave_tree.item(selected[0], "values")
        request_id = int(values[0])
        with self.connect() as con:
            request = con.execute("SELECT employee_id,start_date,end_date,status FROM leave_requests WHERE id=?", (request_id,)).fetchone()
            if not request: return
            emp_id, start, end, old_status = request
            con.execute("UPDATE leave_requests SET status=? WHERE id=?", (new_status, request_id))
            if new_status == "Approved":
                current = datetime.strptime(start, "%Y-%m-%d").date()
                last = datetime.strptime(end, "%Y-%m-%d").date()
                while current <= last:
                    day = current.isoformat()
                    # Do not overwrite a recorded Present or Absent status.
                    con.execute("""INSERT INTO attendance(employee_id,attendance_date,status)
                        VALUES(?,?,'On Leave') ON CONFLICT(employee_id,attendance_date) DO UPDATE SET status='On Leave'
                        WHERE attendance.status='On Leave'""", (emp_id, day))
                    current += timedelta(days=1)
        self.log_action("Leave request status", f"Request {request_id}: {new_status}")
        messagebox.showinfo("Leave updated", f"Request marked {new_status}.")
        self.page_leaves()

    # ---------- HOLIDAY CALENDAR ----------
    def page_holidays(self):
        self.clear_content()
        self.page_heading("Holiday calendar", "Maintain company holidays so the team can plan ahead.")
        panel = tk.Frame(self.content, bg=WHITE, padx=18, pady=16,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        panel.pack(fill="x", pady=(0, 14))
        tk.Label(panel, text="Date (YYYY-MM-DD)", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.holiday_date = tk.Entry(panel, font=("Segoe UI", 10), relief="solid", bd=1)
        self.holiday_date.insert(0, date.today().isoformat())
        self.holiday_date.grid(row=1, column=0, padx=(0, 12), pady=(5, 8), ipady=6, sticky="ew")
        tk.Label(panel, text="Holiday name", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w")
        self.holiday_title = tk.Entry(panel, font=("Segoe UI", 10), relief="solid", bd=1)
        self.holiday_title.grid(row=1, column=1, padx=(0, 12), pady=(5, 8), ipady=6, sticky="ew")
        tk.Label(panel, text="Notes (optional)", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w")
        self.holiday_notes = tk.Entry(panel, font=("Segoe UI", 10), relief="solid", bd=1)
        self.holiday_notes.grid(row=1, column=2, padx=(0, 12), pady=(5, 8), ipady=6, sticky="ew")
        for i in range(3): panel.grid_columnconfigure(i, weight=1)
        actions = tk.Frame(panel, bg=WHITE); actions.grid(row=2, column=0, columnspan=3, sticky="w")
        self.button(actions, "＋ Add holiday", self.add_holiday, bg=PURPLE).pack(side="left", padx=(0, 8))
        self.button(actions, "Delete selected", self.delete_holiday, bg=RED).pack(side="left", padx=8)
        cols = ("id", "date", "day", "title", "notes")
        self.holiday_tree = ttk.Treeview(self.content, columns=cols, show="headings", height=15)
        for col, title, width in [("id","ID",50),("date","Date",130),("day","Day",130),("title","Holiday",250),("notes","Notes",360)]:
            self.holiday_tree.heading(col, text=title); self.holiday_tree.column(col, width=width, anchor="w")
        self.holiday_tree.pack(fill="both", expand=True)
        with self.connect() as con:
            rows = con.execute("SELECT id,holiday_date,title,notes FROM holidays ORDER BY holiday_date").fetchall()
        for row in rows:
            try: day_name = datetime.strptime(row[1], "%Y-%m-%d").strftime("%A")
            except ValueError: day_name = "—"
            self.holiday_tree.insert("", "end", values=(row[0],row[1],day_name,row[2],row[3] or "—"))

    def add_holiday(self):
        d, title, notes = self.holiday_date.get().strip(), self.holiday_title.get().strip(), self.holiday_notes.get().strip()
        try: datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Invalid date", "Use YYYY-MM-DD for the holiday date."); return
        if not title:
            messagebox.showwarning("Holiday name required", "Enter a holiday name."); return
        try:
            with self.connect() as con:
                con.execute("INSERT INTO holidays(holiday_date,title,notes) VALUES(?,?,?)", (d,title,notes))
        except sqlite3.IntegrityError:
            messagebox.showwarning("Date already exists", "A holiday is already registered for this date."); return
        self.log_action("Add holiday", f"{d}: {title}")
        self.page_holidays()

    def delete_holiday(self):
        selected = self.holiday_tree.selection() if hasattr(self, "holiday_tree") else ()
        if not selected:
            messagebox.showwarning("Select holiday", "Choose a holiday to delete."); return
        values = self.holiday_tree.item(selected[0], "values")
        if not messagebox.askyesno("Confirm delete", f"Delete {values[3]} on {values[1]}?"): return
        with self.connect() as con:
            con.execute("DELETE FROM holidays WHERE id=?", (int(values[0]),))
        self.log_action("Delete holiday", f"{values[1]}: {values[3]}")
        self.page_holidays()

    # ---------- TEAM ANALYTICS ----------
    def page_analytics(self):
        self.clear_content()
        month = date.today().strftime("%Y-%m")
        self.page_heading("Team analytics", "Department comparison, attendance leaderboard, working hours, and attention flags.")
        with self.connect() as con:
            departments = con.execute("""SELECT COALESCE(NULLIF(e.department,''),'Unassigned') AS dept,
                COUNT(DISTINCT e.id), SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END),
                SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END),
                SUM(CASE WHEN a.status='On Leave' THEN 1 ELSE 0 END)
                FROM employees e LEFT JOIN attendance a ON a.employee_id=e.id AND a.attendance_date LIKE ?
                GROUP BY dept ORDER BY COUNT(DISTINCT e.id) DESC, dept""", (month + "%",)).fetchall()
            employee_rows = con.execute("""SELECT e.id,e.name,COALESCE(e.department,'Unassigned'),
                SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS p,
                SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) AS ab
                FROM employees e LEFT JOIN attendance a ON a.employee_id=e.id AND a.attendance_date LIKE ?
                GROUP BY e.id,e.name,e.department ORDER BY e.name""", (month + "%",)).fetchall()
            audit = con.execute("SELECT created_at,username,action,details FROM audit_logs ORDER BY id DESC LIMIT 12").fetchall()
        summary = tk.Frame(self.content, bg=BG); summary.pack(fill="x", pady=(0, 14))
        total_people = len(employee_rows)
        rated = [(r[1], r[2], r[3], r[4], (r[3] / (r[3] + r[4]) * 100 if r[3] + r[4] else 0)) for r in employee_rows]
        overall_p = sum(r[2] for r in rated); overall_a = sum(r[3] for r in rated)
        overall = overall_p / (overall_p + overall_a) * 100 if overall_p + overall_a else 0
        for i, (title,value,color,sub) in enumerate([
            ("TEAM SIZE",total_people,PURPLE,"Active employee records"),
            ("MONTHLY ATTENDANCE",f"{overall:.1f}%",TEAL,month),
            ("TOP ATTENDANCE",f"{max([r[4] for r in rated], default=0):.1f}%",GREEN,"Best employee rate"),
            ("NEEDS ATTENTION",sum(1 for r in rated if r[2]+r[3] and r[4]<75),RED,"Below 75% attendance")]):
            c=self.card(summary,title,value,color,sub); c.grid(row=0,column=i,sticky="nsew",padx=(0 if i==0 else 8,0)); summary.grid_columnconfigure(i,weight=1,uniform="analytics")
        split = tk.Frame(self.content, bg=BG); split.pack(fill="both", expand=True)
        left = tk.Frame(split,bg=WHITE,padx=14,pady=14,highlightbackground="#E5E9F2",highlightthickness=1)
        left.pack(side="left",fill="both",expand=True,padx=(0,10))
        tk.Label(left,text=f"Department overview · {month}",bg=WHITE,fg=TEXT,font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,8))
        dcols=("dept","people","present","absent","leave","rate")
        dt=ttk.Treeview(left,columns=dcols,show="headings",height=7)
        for col,title,width in [("dept","Department",145),("people","Team",55),("present","Present",65),("absent","Absent",65),("leave","Leave",60),("rate","Rate",70)]: dt.heading(col,text=title);dt.column(col,width=width,anchor="w")
        dt.pack(fill="both",expand=True)
        for dept,people,pres,absent,leave in departments:
            pres,absent,leave=pres or 0,absent or 0,leave or 0
            denom=pres+absent; rate=pres/denom*100 if denom else 0
            dt.insert("","end",values=(dept,people,pres,absent,leave,f"{rate:.1f}%"))
        right = tk.Frame(split,bg=WHITE,padx=14,pady=14,width=390,highlightbackground="#E5E9F2",highlightthickness=1)
        right.pack(side="right",fill="y"); right.pack_propagate(False)
        tk.Label(right,text="Attendance leaderboard",bg=WHITE,fg=TEXT,font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,8))
        board=ttk.Treeview(right,columns=("name","rate","days"),show="headings",height=7)
        for col,title,width in [("name","Employee",175),("rate","Rate",75),("days","P/A",70)]: board.heading(col,text=title);board.column(col,width=width,anchor="w")
        board.pack(fill="both",expand=True)
        for name,dept,pres,absent,rate in sorted(rated,key=lambda x:(-x[4],x[0]))[:12]:
            board.insert("","end",values=(name,f"{rate:.1f}%",f"{pres}/{absent}"))
        tk.Label(right,text="Recent admin activity",bg=WHITE,fg=TEXT,font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(14,5))
        for created,username,action,details in audit[:5]:
            tk.Label(right,text=f"{created} · {username}\n{action}: {details or ''}",bg=WHITE,fg=MUTED,font=("Segoe UI",8),justify="left",wraplength=345).pack(anchor="w",pady=3)
        self.button(self.content,"Refresh analytics",self.page_analytics,bg="#E9EDFA",fg=TEXT).pack(anchor="w",pady=(12,0))

    def backup_database(self):
        source = os.path.abspath(DB_NAME)
        if not os.path.exists(source):
            messagebox.showwarning("No database", "The database file was not found yet."); return
        path = filedialog.asksaveasfilename(defaultextension=".db", initialfile=f"employee_backup_{date.today().isoformat()}.db",
                                            filetypes=[("SQLite database", "*.db")])
        if not path: return
        try:
            # Use SQLite's backup API to create a consistent copy even if the app is open.
            with self.connect() as con:
                target = sqlite3.connect(path)
                try: con.backup(target)
                finally: target.close()
            messagebox.showinfo("Backup complete", f"Database backup saved to:\n{path}")
            self.log_action("Database backup", path)
        except (OSError, sqlite3.Error) as exc:
            messagebox.showerror("Backup failed", str(exc))

    # ---------- REPORTS ----------
    def page_reports(self):
        self.clear_content()
        self.page_heading("Reports & insights", "Review attendance trends and export your records.")
        today = date.today().isoformat()
        month = date.today().strftime("%Y-%m")
        with self.connect() as con:
            total = con.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
            month_records = con.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date LIKE ?", (month + "%",)).fetchone()[0]
            month_present = con.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date LIKE ? AND status='Present'", (month + "%",)).fetchone()[0]
            month_absent = con.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date LIKE ? AND status='Absent'", (month + "%",)).fetchone()[0]
            month_leave = con.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date LIKE ? AND status='On Leave'", (month + "%",)).fetchone()[0]
            rows = con.execute("""
                SELECT e.name, e.department, a.attendance_date, a.status, a.check_in, a.check_out
                FROM attendance a JOIN employees e ON e.id=a.employee_id
                WHERE a.attendance_date LIKE ?
                ORDER BY a.attendance_date DESC, e.name
            """, (month + "%",)).fetchall()
        summary = tk.Frame(self.content, bg=BG)
        summary.pack(fill="x", pady=(0, 18))
        for i, (title, value, color) in enumerate([
            ("Team size", total, PURPLE), ("Records this month", month_records, BLUE),
            ("Present records", month_present, GREEN), ("Absent records", month_absent, RED),
            ("Leave records", month_leave, ORANGE)
        ]):
            c = self.card(summary, title, value, color, month)
            c.grid(row=0, column=i, sticky="nsew", padx=(0, 7))
            summary.grid_columnconfigure(i, weight=1, uniform="reportcards")

        panel = tk.Frame(self.content, bg=WHITE, padx=20, pady=20,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        panel.pack(fill="x", pady=(0, 18))
        tk.Label(panel, text="Monthly snapshot", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        denominator = month_present + month_absent + month_leave
        present_pct = (month_present / denominator * 100) if denominator else 0
        tk.Label(panel, text=f"{month}  •  {month_records} attendance records  •  "
                 f"{present_pct:.1f}% of recorded statuses are Present",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 11)).pack(anchor="w", pady=(9, 14))
        bar = tk.Frame(panel, bg="#E9EDFA", height=18)
        bar.pack(fill="x")
        if denominator:
            tk.Frame(bar, bg=GREEN, width=1).place(relx=0, rely=0, relwidth=month_present/denominator, relheight=1)
            tk.Frame(bar, bg=RED).place(relx=month_present/denominator, rely=0,
                                        relwidth=month_absent/denominator, relheight=1)
            tk.Frame(bar, bg=ORANGE).place(relx=(month_present+month_absent)/denominator,
                                           rely=0, relwidth=month_leave/denominator, relheight=1)
        tk.Label(panel, text="Green = Present     Red = Absent     Orange = On Leave",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(9, 0))
        buttons = tk.Frame(self.content, bg=BG)
        buttons.pack(anchor="w")
        self.button(buttons, "Export monthly CSV", lambda: self.export_csv(rows, f"attendance_{month}.csv"), bg=PURPLE).pack(side="left", padx=(0, 10))
        self.button(buttons, "Export all attendance", lambda: self.export_all_csv(), bg=BLUE).pack(side="left", padx=(0, 10))
        self.button(buttons, "Backup database", self.backup_database, bg=TEAL).pack(side="left")

    def export_csv(self, rows, default_name):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                    initialfile=default_name, filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["Employee", "Department", "Date", "Status", "Check-in", "Check-out", "Working hours"])
                for row in rows:
                    writer.writerow(list(row) + [self.hours_between(row[4], row[5])])
            messagebox.showinfo("Export complete", f"CSV report saved to:\n{path}")
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))

    def export_all_csv(self):
        with self.connect() as con:
            rows = con.execute("""
                SELECT e.name, e.department, a.attendance_date, a.status, a.check_in, a.check_out
                FROM attendance a JOIN employees e ON e.id=a.employee_id
                ORDER BY a.attendance_date DESC, e.name
            """).fetchall()
        self.export_csv(rows, "all_attendance.csv")

    # ---------- ADMIN SETTINGS ----------
    def page_admin(self):
        self.clear_content()
        self.page_heading("Admin settings", "Change your password and manage your sign-in details.")
        panel = tk.Frame(self.content, bg=WHITE, padx=24, pady=24,
                         highlightbackground="#E5E9F2", highlightthickness=1)
        panel.pack(fill="x", anchor="n")
        tk.Label(panel, text="Change admin password", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 6))
        tk.Label(panel, text="Use a strong password and keep it private.",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 20))
        self.old_pass = tk.Entry(panel, show="•", font=("Segoe UI", 11), width=38, relief="solid", bd=1)
        self.new_pass = tk.Entry(panel, show="•", font=("Segoe UI", 11), width=38, relief="solid", bd=1)
        self.confirm_pass = tk.Entry(panel, show="•", font=("Segoe UI", 11), width=38, relief="solid", bd=1)
        for title, ent in [("Current password", self.old_pass), ("New password (minimum 8 characters)", self.new_pass), ("Confirm new password", self.confirm_pass)]:
            tk.Label(panel, text=title, bg=WHITE, fg=MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 5))
            ent.pack(anchor="w", ipady=7)
        self.button(panel, "Update password", self.change_password, bg=PURPLE).pack(anchor="w", pady=(20, 0))

    def change_password(self):
        old = self.old_pass.get()
        new = self.new_pass.get()
        confirm = self.confirm_pass.get()
        if len(new) < 8:
            messagebox.showwarning("Password too short", "Use at least 8 characters.")
            return
        if new != confirm:
            messagebox.showwarning("Password mismatch", "The new passwords do not match.")
            return
        with self.connect() as con:
            row = con.execute("SELECT password_hash FROM admins WHERE username=?",
                              (self.current_admin,)).fetchone()
            if not row or row[0] != hash_password(old):
                messagebox.showerror("Incorrect password", "Your current password is incorrect.")
                return
            con.execute("UPDATE admins SET password_hash=? WHERE username=?",
                        (hash_password(new), self.current_admin))
        self.old_pass.delete(0, "end")
        self.new_pass.delete(0, "end")
        self.confirm_pass.delete(0, "end")
        self.log_action("Change password", "Admin password updated")
        messagebox.showinfo("Password updated", "Your admin password has been changed.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AttendanceApp(root)
    root.mainloop()
