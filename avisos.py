"""Avisos locales agrupados. No hace consultas a ChileCompra ni guarda tickets."""
import json
import threading
import time
import webbrowser

from sync import iso, now


class AlertCenter:
    def __init__(self, store):
        self.store = store
        self.desktop_active = False
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS avisos_conocidos (codigo TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS avisos (
                    codigo TEXT PRIMARY KEY, titulo TEXT NOT NULL,
                    detectado_en TEXT NOT NULL, lugares TEXT NOT NULL,
                    mostrado INTEGER NOT NULL DEFAULT 0
                );
            ''')

    def observe(self, results):
        """First observation is a silent baseline. Later additions become events."""
        date = iso(now())
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            seeded = db.execute("SELECT valor FROM meta WHERE clave='avisos_inicializados'").fetchone()
            count = 0
            for result in results:
                code = result['id']
                inserted = db.execute('INSERT OR IGNORE INTO avisos_conocidos VALUES (?)', (code,)).rowcount
                if inserted and seeded:
                    db.execute('INSERT OR IGNORE INTO avisos(codigo,titulo,detectado_en,lugares) VALUES (?,?,?,?)',
                               (code, str(result.get('titulo') or 'Título no informado'), date,
                                json.dumps(result.get('donde_coincide') or [], ensure_ascii=False)))
                    count += 1
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('avisos_inicializados', 'si'))
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('avisos_ultima_revision', date))
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('avisos_error', ''))
        return count

    def enabled(self):
        return self.store.metadata().get('avisos_habilitados', 'si') == 'si'

    def set_enabled(self, value):
        self.store.set_meta(avisos_habilitados='si' if value else 'no')

    def history(self, pending_only=False):
        with self.store.connect() as db:
            rows = db.execute('SELECT codigo,titulo,detectado_en,lugares,mostrado FROM avisos '
                              + ('WHERE mostrado=0 ' if pending_only else '')
                              + 'ORDER BY detectado_en DESC,codigo').fetchall()
        return [{'id': c, 'titulo': t, 'detectado_en': d, 'donde_coincide': json.loads(l), 'mostrado': bool(m)} for c, t, d, l, m in rows]

    def mark_shown(self, codes):
        with self.store.connect() as db:
            db.executemany('UPDATE avisos SET mostrado=1 WHERE codigo=?', [(c,) for c in codes])

    def start(self, loader):
        def loop():
            while True:
                try:
                    self.observe(loader()['resultados'])
                except Exception:
                    self.store.set_meta(avisos_error='No se pudo revisar la caché para generar avisos. No se confirmó una revisión nueva.')
                time.sleep(60)
        thread = threading.Thread(target=loop, daemon=True, name='avisos-cache')
        thread.start()
        return thread


def desktop_alerts(center, port=8000):
    """Tk event loop on the main thread; one popup groups all new detections."""
    import tkinter as tk
    from tkinter import messagebox
    try:
        root = tk.Tk()
    except tk.TclError:
        raise RuntimeError('No hay una pantalla gráfica disponible.') from None
    root.title('Buscador de Pendones · Avisos en pantalla')
    center.desktop_active = True
    root.geometry('620x510')
    tk.Label(root, text='Avisos de nuevas coincidencias', font=('Arial', 15, 'bold')).pack(pady=(18, 8))
    tk.Label(root, text='El programa debe permanecer abierto. No necesita tener abierta la página.', wraplength=570).pack()
    tk.Label(root, text='Una nueva detección puede ser una compra antigua cuyos ítems acaban de descargarse.', wraplength=570).pack(pady=8)
    enabled = tk.BooleanVar(value=center.enabled())
    tk.Checkbutton(root, text='Activar avisos en pantalla', variable=enabled,
                   command=lambda: center.set_enabled(enabled.get())).pack()
    status = tk.Label(root, wraplength=570, justify=tk.LEFT)
    status.pack(padx=20, pady=12)
    buttons = tk.Frame(root)
    buttons.pack(pady=8)
    tk.Button(buttons, text='Abrir compras', command=lambda: webbrowser.open(f'http://127.0.0.1:{port}/monitor')).pack(side=tk.LEFT, padx=6)
    tk.Button(buttons, text='Menores a $100.000', command=lambda: webbrowser.open(f'http://127.0.0.1:{port}/menores-100000')).pack(side=tk.LEFT, padx=6)
    tk.Button(buttons, text='Ver historial de avisos', command=lambda: webbrowser.open(f'http://127.0.0.1:{port}/avisos')).pack(side=tk.LEFT, padx=6)
    tk.Button(root, text='Segundo llamado · Menos de $500.000', command=lambda: webbrowser.open(f'http://127.0.0.1:{port}/segundo-llamado-500000')).pack(pady=6)
    tk.Button(root, text='Pin o pines - ver y descargar Excel', command=lambda: webbrowser.open(f'http://127.0.0.1:{port}/pines')).pack(pady=6)
    tk.Button(root, text='Difusion - ver y descargar Excel', command=lambda: webbrowser.open(f'http://127.0.0.1:{port}/difusion')).pack(pady=6)
    tk.Button(root, text='Banderas vela - ver y descargar Excel', command=lambda: webbrowser.open(f'http://127.0.0.1:{port}/banderas-vela')).pack(pady=6)
    popup = None

    def tick():
        nonlocal popup
        try:
            meta = center.store.metadata()
            counts = center.store.counts()
            enabled.set(center.enabled())
            status.config(text=f"Sincronización: {meta.get('estado', 'iniciando')}. Detalles pendientes: {counts['detalles_pendientes']}.\n{meta.get('error') or meta.get('avisos_error') or 'Sin errores registrados.'}")
            events = center.history(pending_only=True) if center.enabled() else []
            if events:
                if popup is not None and popup.winfo_exists():
                    popup.destroy()
                popup = tk.Toplevel(root)
                popup.title('Nuevas coincidencias de pendones')
                popup.geometry('600x290')
                tk.Label(popup, text=f'{len(events)} nuevas coincidencias detectadas', font=('Arial', 14, 'bold')).pack(pady=16)
                lines = '\n'.join(f"{e['id']} · {e['titulo'][:120]}" for e in events[:3])
                tk.Label(popup, text=lines, wraplength=550, justify=tk.LEFT).pack(padx=20, pady=8)
                tk.Label(popup, text='Verifica la vigencia y los requisitos antes de ofertar.', wraplength=550).pack(pady=6)
                tk.Button(popup, text='Ver avisos y compras', command=lambda: webbrowser.open(f'http://127.0.0.1:{port}/avisos')).pack(pady=8)
                popup.lift()
                center.mark_shown([e['id'] for e in events])
        except Exception:
            status.config(text='No se pudo actualizar el panel de avisos. Revisa el diagnóstico del buscador.')
        root.after(2000, tick)

    def close():
        if messagebox.askyesno('Cerrar buscador', '¿Cerrar el programa y detener las búsquedas y los avisos?', parent=root):
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(1000, tick)
    try:
        root.mainloop()
    finally:
        center.desktop_active = False
