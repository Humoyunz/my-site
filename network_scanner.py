import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import socket
from ipaddress import ip_network
import subprocess
import platform
import csv
from threading import Thread
from queue import Queue
import time
import os
import re

# -------------------
# Кроссплатформенный звук
# -------------------
def play_beep():
    system = platform.system().lower()
    try:
        if system == "windows":
            import winsound
            winsound.Beep(1000, 30)
        elif system == "darwin":
            os.system('afplay /System/Library/Sounds/Glass.aiff')
        else:  # Linux
            os.system('beep -f 1000 -l 30')
    except:
        pass

# -------------------
# Определяем локальную сеть автоматически
# -------------------
def get_local_subnet():
    system = platform.system().lower()
    local_ip = None
    try:
        if system == "windows":
            output = subprocess.check_output("ipconfig").decode()
            match = re.search(r"IPv4 Address[.\s]*:\s*([\d.]+)", output)
            if match:
                local_ip = match.group(1)
        elif system == "darwin" or system == "linux":
            output = subprocess.check_output("ifconfig").decode()
            matches = re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", output)
            for ip in matches:
                if ip != "127.0.0.1":
                    local_ip = ip
                    break
        if local_ip:
            parts = local_ip.split(".")
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    except:
        pass
    return "192.168.1.0/24"  # запасной вариант

# -------------------
# Функции сканера
# -------------------
def ping_host(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", param, "1", ip]
    try:
        return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except:
        return False

def scan_port(ip, port, timeout=1):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def export_to_csv(results, filename):
    try:
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ["IP", "Status", "Ports"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                row_copy = row.copy()
                row_copy["Ports"] = ", ".join(str(p) for p in row_copy["Ports"])
                writer.writerow(row_copy)
        messagebox.showinfo("Экспорт", f"Результаты сохранены в {filename}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {e}")

# -------------------
# GUI
# -------------------
def start_gui():
    root = tk.Tk()
    root.title("🕵️ Safe Practice Agent Scanner")
    root.geometry("750x550")
    root.configure(bg="#121212")

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview",
                    background="#1e1e1e",
                    foreground="white",
                    fieldbackground="#1e1e1e",
                    font=("Consolas", 10))
    style.configure("Treeview.Heading",
                    background="#1e1e1e",
                    foreground="cyan",
                    font=("Consolas", 11, "bold"))

    tree = ttk.Treeview(root)
    tree["columns"] = ("IP", "Status", "Ports")
    tree.heading("#0", text="")
    tree.column("#0", width=0, stretch=False)
    for col in tree["columns"]:
        tree.heading(col, text=col)
        tree.column(col, anchor="center", width=220)
    tree.pack(fill="both", expand=True, pady=10, padx=10)

    progress = ttk.Progressbar(root, orient="horizontal", length=700, mode="determinate")
    progress.pack(pady=5)

    cursor_label = tk.Label(root, text="", fg="cyan", bg="#121212", font=("Consolas", 12))
    cursor_label.pack(pady=2)

    results = []

    # -------------------
    # Мигающий курсор
    # -------------------
    def blink_cursor():
        while True:
            cursor_label.config(text="_")
            time.sleep(0.5)
            cursor_label.config(text="")
            time.sleep(0.5)

    Thread(target=blink_cursor, daemon=True).start()

    # -------------------
    # Сканирование сети (локальная + учебная “внешняя”)
    # -------------------
    def threaded_scan():
        nonlocal results
        tree.delete(*tree.get_children())

        # Автоматическая подсеть
        subnet = get_local_subnet()
        # Учебные внешние IP (например, виртуальные тестовые сервера в сети)
        virtual_subnet = "10.10.10.0/30"  # можно поднять VM/контейнеры для тренировки
        combined_ips = list(ip_network(subnet)) + list(ip_network(virtual_subnet))
        total = len(combined_ips)
        progress["maximum"] = total
        results = []

        queue = Queue()

        def worker(ip):
            status = "Online" if ping_host(ip) else "Offline"
            open_ports = []
            if status == "Online":
                for port in [22, 80, 443]:
                    if scan_port(ip, port):
                        open_ports.append(port)
            queue.put({"IP": ip, "Status": status, "Ports": open_ports})

        threads = []
        for ip in combined_ips:
            t = Thread(target=worker, args=(str(ip),))
            t.start()
            threads.append(t)
            if len(threads) >= 50:
                for th in threads:
                    th.join()
                threads = []
        for th in threads:
            th.join()

        # -------------------
        # Эффект печатающегося терминала с звуком
        # -------------------
        while not queue.empty():
            res = queue.get()
            results.append(res)
            ports_str = ""
            item_id = tree.insert("", "end", values=("", "", ""))
            if res["Status"] == "Online":
                tree.item(item_id, tags=("online",))
            else:
                tree.item(item_id, tags=("offline",))
            tree.tag_configure("online", background="#0f3")
            tree.tag_configure("offline", background="#333")

            # Печатаем IP
            display_ip = ""
            for ch in res["IP"]:
                display_ip += ch
                tree.set(item_id, "IP", display_ip)
                root.update_idletasks()
                time.sleep(0.02)

            # Печатаем статус
            display_status = ""
            for ch in res["Status"]:
                display_status += ch
                tree.set(item_id, "Status", display_status)
                root.update_idletasks()
                time.sleep(0.02)

            # Печатаем порты с эффектом звука
            for port in res["Ports"]:
                ports_str += f"{port} "
                tree.set(item_id, "Ports", ports_str.strip())
                root.update_idletasks()
                time.sleep(0.05)
                play_beep()

            progress["value"] += 1
            root.update_idletasks()
            time.sleep(0.03)

        progress["value"] = 0
        cursor_label.config(text="")

    # -------------------
    # Кнопки
    # -------------------
    def start_scan():
        Thread(target=threaded_scan).start()

    def save_results():
        if not results:
            messagebox.showwarning("Внимание", "Нет данных для сохранения!")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".csv",
                                                filetypes=[("CSV files", "*.csv")])
        if filename:
            export_to_csv(results, filename)

    btn_frame = tk.Frame(root, bg="#121212")
    btn_frame.pack(pady=5)

    scan_btn = tk.Button(btn_frame, text="🛰 Сканировать сеть", command=start_scan,
                         bg="#1f1f1f", fg="cyan", font=("Consolas", 11, "bold"),
                         relief="flat", padx=10, pady=5)
    scan_btn.pack(side="left", padx=10)

    save_btn = tk.Button(btn_frame, text="💾 Экспорт в CSV", command=save_results,
                         bg="#1f1f1f", fg="cyan", font=("Consolas", 11, "bold"),
                         relief="flat", padx=10, pady=5)
    save_btn.pack(side="left", padx=10)

    root.mainloop()

# -------------------
# Запуск
# -------------------
if __name__ == "__main__":
    start_gui()
