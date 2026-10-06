"""Tkinter user interface for the P2P network assignment."""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from p2p_node import P2PNode


class P2PApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Peer-to-Peer Network")
        self.root.geometry("760x620")
        self.events = queue.Queue()
        self.node = None
        self.peer_rows = {}

        startup = ttk.LabelFrame(root, text="My Peer")
        startup.pack(fill="x", padx=10, pady=(10, 5))
        self.name = tk.StringVar(value="Peer")
        self.listen_port = tk.StringVar(value="5000")
        ttk.Label(startup, text="Name:").grid(row=0, column=0, padx=5, pady=7)
        ttk.Entry(startup, textvariable=self.name, width=18).grid(row=0, column=1, padx=5)
        ttk.Label(startup, text="Port:").grid(row=0, column=2, padx=5)
        ttk.Entry(startup, textvariable=self.listen_port, width=10).grid(row=0, column=3, padx=5)
        self.start_button = ttk.Button(startup, text="Start Peer", command=self.start_peer)
        self.start_button.grid(row=0, column=4, padx=5)
        self.stop_button = ttk.Button(startup, text="Stop", command=self.stop_peer, state="disabled")
        self.stop_button.grid(row=0, column=5, padx=5)

        connect = ttk.LabelFrame(root, text="Connect to Another Peer")
        connect.pack(fill="x", padx=10, pady=5)
        self.remote_ip = tk.StringVar(value="127.0.0.1")
        self.remote_port = tk.StringVar(value="5001")
        ttk.Label(connect, text="IP:").grid(row=0, column=0, padx=5, pady=7)
        ttk.Entry(connect, textvariable=self.remote_ip, width=22).grid(row=0, column=1, padx=5)
        ttk.Label(connect, text="Port:").grid(row=0, column=2, padx=5)
        ttk.Entry(connect, textvariable=self.remote_port, width=10).grid(row=0, column=3, padx=5)
        self.connect_button = ttk.Button(connect, text="Connect", command=self.connect_peer, state="disabled")
        self.connect_button.grid(row=0, column=4, padx=5)

        middle = ttk.Frame(root)
        middle.pack(fill="both", expand=True, padx=10, pady=5)
        peers_frame = ttk.LabelFrame(middle, text="Connected Peers")
        peers_frame.pack(side="left", fill="y", padx=(0, 5))
        self.peer_list = tk.Listbox(peers_frame, width=25, exportselection=False)
        self.peer_list.pack(fill="both", expand=True, padx=5, pady=5)
        log_frame = ttk.LabelFrame(middle, text="Messages / Events")
        log_frame.pack(side="left", fill="both", expand=True)
        self.log = tk.Text(log_frame, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        scrollbar.pack(side="right", fill="y", pady=5, padx=(0, 5))

        send = ttk.LabelFrame(root, text="Send Text")
        send.pack(fill="x", padx=10, pady=5)
        self.message = tk.StringVar()
        self.message_entry = ttk.Entry(send, textvariable=self.message)
        self.message_entry.pack(side="left", fill="x", expand=True, padx=5, pady=7)
        self.send_button = ttk.Button(send, text="Send", command=self.send_text, state="disabled")
        self.send_button.pack(side="left", padx=5)
        self.file_button = ttk.Button(root, text="Choose File & Send", command=self.send_file, state="disabled")
        self.file_button.pack(anchor="w", padx=15, pady=(0, 10))

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.process_events)

    def emit(self, event):
        self.events.put(event)

    def start_peer(self):
        peer_name = self.name.get().strip()
        try:
            port = int(self.listen_port.get())
            if not peer_name:
                raise ValueError("Enter a peer name")
            if not 1 <= port <= 65535:
                raise ValueError("Port must be between 1 and 65535")
            node = P2PNode(peer_name, self.emit)
            node.start(port)
        except (ValueError, OSError, RuntimeError) as exc:
            messagebox.showerror("Unable to start peer", str(exc))
            return
        self.node = node
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.connect_button.configure(state="normal")
        self.refresh_peers()

    def stop_peer(self):
        if self.node:
            self.node.stop()
            self.node = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.connect_button.configure(state="disabled")
        self.send_button.configure(state="disabled")
        self.file_button.configure(state="disabled")
        self.refresh_peers()

    def connect_peer(self):
        try:
            host = self.remote_ip.get().strip()
            port = int(self.remote_port.get())
            if not host or not 1 <= port <= 65535:
                raise ValueError("Enter a valid IP address and port")
        except ValueError as exc:
            messagebox.showerror("Invalid peer address", str(exc))
            return
        self.connect_button.configure(state="disabled")
        threading.Thread(target=self._connect_worker, args=(host, port), daemon=True).start()

    def _connect_worker(self, host, port):
        try:
            self.node.connect(host, port)
        except (OSError, ValueError, RuntimeError) as exc:
            self.emit(f"[ERROR] Connection failed: {exc}")
        finally:
            self.events.put(("refresh", None))

    def selected_peer_id(self):
        selection = self.peer_list.curselection()
        if not selection:
            raise ValueError("Select a connected peer first")
        return self.peer_rows[selection[0]][0]

    def send_text(self):
        text = self.message.get()
        if not text.strip():
            return
        try:
            peer_id = self.selected_peer_id()
            self.node.send_text(peer_id, text)
            self.message.set("")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Unable to send message", str(exc))

    def send_file(self):
        path = filedialog.askopenfilename(title="Choose a file to send")
        if not path:
            return
        try:
            peer_id = self.selected_peer_id()
        except ValueError as exc:
            messagebox.showerror("Unable to send file", str(exc))
            return
        threading.Thread(target=self._file_worker, args=(peer_id, path), daemon=True).start()

    def _file_worker(self, peer_id, path):
        try:
            self.node.send_file(peer_id, path)
        except (OSError, ValueError) as exc:
            self.emit(f"[ERROR] File transfer failed: {exc}")

    def refresh_peers(self):
        selected = self.selected_peer_id_safe()
        peers = self.node.connected_peers() if self.node else []
        self.peer_rows = peers
        self.peer_list.delete(0, tk.END)
        for peer_id, name in peers:
            self.peer_list.insert(tk.END, f"{name} [{peer_id}]")
            if peer_id == selected:
                self.peer_list.selection_set(tk.END)
        state = "normal" if peers else "disabled"
        self.send_button.configure(state=state)
        self.file_button.configure(state=state)

    def selected_peer_id_safe(self):
        selection = self.peer_list.curselection()
        if selection and selection[0] < len(self.peer_rows):
            return self.peer_rows[selection[0]][0]
        return None

    def process_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, tuple) and event[0] == "refresh":
                self.refresh_peers()
                self.connect_button.configure(state="normal" if self.node else "disabled")
                continue
            self.log.configure(state="normal")
            self.log.insert(tk.END, str(event) + "\n")
            self.log.see(tk.END)
            self.log.configure(state="disabled")
            self.refresh_peers()
        self.root.after(100, self.process_events)

    def close(self):
        self.stop_peer()
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    P2PApplication(window)
    window.mainloop()
