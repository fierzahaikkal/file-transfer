import socket
import threading
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("server_log.txt"), logging.StreamHandler()]
)

# Define server default settings
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 12345
BUFFER_SIZE = 4096

class FileServer:
    def __init__(self):
        self.server_socket = None
        self.is_running = False
        self.connected_clients = []
        self.transfer_history = []
    
    def start(self, host, port, callback=None):
        """Start the server on the specified host and port"""
        if self.is_running:
            return False
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set socket option to reuse address
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((host, port))
            self.server_socket.listen(5)
            self.is_running = True
            
            # Start listening for connections in a separate thread
            threading.Thread(target=self._listen_for_clients, 
                            args=(callback,), 
                            daemon=True).start()
            
            logging.info(f"Server started on {host}:{port}")
            return True
        except Exception as e:
            logging.error(f"Failed to start server: {str(e)}")
            return False
    
    def stop(self):
        """Stop the server and close all connections"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Close all client connections
        for client in self.connected_clients:
            try:
                client.close()
            except:
                pass
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        self.connected_clients = []
        logging.info("Server stopped")
    
    def _listen_for_clients(self, callback=None):
        """Listen for client connections"""
        while self.is_running:
            try:
                client_socket, client_address = self.server_socket.accept()
                self.connected_clients.append(client_socket)
                
                client_info = f"{client_address[0]}:{client_address[1]}"
                logging.info(f"Accepted connection from {client_info}")
                
                if callback:
                    callback(client_info)
            except Exception as e:
                if self.is_running:  # Only log if we're still supposed to be running
                    logging.error(f"Error accepting connection: {str(e)}")
                break
    
    def send_file(self, client_socket, file_path, progress_callback=None):
        """Send a file to a client"""
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            # Send file info (name and size) first
            header = f"{file_name}|{file_size}"
            client_socket.sendall(header.encode() + b"\n")
            
            sent_bytes = 0
            with open(file_path, 'rb') as file:
                while True:
                    data = file.read(BUFFER_SIZE)
                    if not data:
                        break
                    
                    client_socket.sendall(data)
                    sent_bytes += len(data)
                    
                    if progress_callback:
                        progress = int((sent_bytes / file_size) * 100)
                        progress_callback(progress)
            
            # Record successful transfer
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            client_info = client_socket.getpeername()
            client_addr = f"{client_info[0]}:{client_info[1]}"
            transfer_record = {
                "timestamp": timestamp,
                "file": file_name,
                "size": file_size,
                "client": client_addr,
                "status": "Complete"
            }
            self.transfer_history.append(transfer_record)
            logging.info(f"File '{file_name}' sent successfully to {client_addr}")
            return True
            
        except Exception as e:
            logging.error(f"Error sending file: {str(e)}")
            # Record failed transfer
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            client_info = client_socket.getpeername()
            client_addr = f"{client_info[0]}:{client_info[1]}"
            transfer_record = {
                "timestamp": timestamp,
                "file": os.path.basename(file_path),
                "size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                "client": client_addr,
                "status": f"Failed: {str(e)}"
            }
            self.transfer_history.append(transfer_record)
            return False


class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced File Transfer Server")
        self.root.geometry("800x600")
        self.root.minsize(600, 500)
        
        # Set up the server
        self.file_server = FileServer()
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')  # Use a modern looking theme
        
        # Configure colors
        bg_color = "#f5f5f5"
        accent_color = "#1976d2"
        
        self.style.configure("TButton", padding=6, font=("Segoe UI", 10))
        self.style.configure("TLabel", font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        self.style.configure("Status.TLabel", font=("Segoe UI", 9))
        
        self.root.configure(bg=bg_color)
        
        # Variables
        self.selected_file = tk.StringVar()
        self.server_status = tk.StringVar(value="Server Stopped")
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.server_running = False
        
        # Create frames
        self.create_main_layout()
        
        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_main_layout(self):
        """Create the main application layout"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Setup paned window for resizable sections
        paned_window = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned_window.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Top section - Server controls
        top_frame = ttk.LabelFrame(paned_window, text="Server Settings", padding="10")
        paned_window.add(top_frame, weight=1)
        
        # Server settings
        settings_frame = ttk.Frame(top_frame)
        settings_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(settings_frame, text="Host:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        host_entry = ttk.Entry(settings_frame, textvariable=self.host_var, width=15)
        host_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Port:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        port_entry = ttk.Entry(settings_frame, textvariable=self.port_var, width=8)
        port_entry.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)
        
        # Server control buttons
        controls_frame = ttk.Frame(top_frame)
        controls_frame.pack(fill=tk.X, pady=10)
        
        self.start_button = ttk.Button(controls_frame, text="Start Server", command=self.toggle_server)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.select_button = ttk.Button(controls_frame, text="Select File", command=self.select_file)
        self.select_button.pack(side=tk.LEFT, padx=5)
        self.select_button.config(state=tk.DISABLED)
        
        # Status section
        status_frame = ttk.Frame(top_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(status_frame, textvariable=self.server_status, style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Selected file frame
        file_frame = ttk.LabelFrame(top_frame, text="Selected File", padding="10")
        file_frame.pack(fill=tk.X, pady=10)
        
        self.file_label = ttk.Label(file_frame, text="No file selected", font=("Segoe UI", 9))
        self.file_label.pack(fill=tk.X)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(paned_window)
        paned_window.add(notebook, weight=3)
        
        # Clients tab
        self.clients_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.clients_frame, text="Connected Clients")
        
        # Create client tree view
        client_tree_frame = ttk.Frame(self.clients_frame)
        client_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        client_scroll = ttk.Scrollbar(client_tree_frame)
        client_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.client_tree = ttk.Treeview(client_tree_frame, columns=("client", "status"), 
                                        show="headings", yscrollcommand=client_scroll.set)
        self.client_tree.heading("client", text="Client")
        self.client_tree.heading("status", text="Status")
        self.client_tree.column("client", width=200)
        self.client_tree.column("status", width=100)
        self.client_tree.pack(fill=tk.BOTH, expand=True)
        
        client_scroll.config(command=self.client_tree.yview)
        
        # Transfer History tab
        self.history_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.history_frame, text="Transfer History")
        
        # Create history tree view
        history_tree_frame = ttk.Frame(self.history_frame)
        history_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        history_scroll = ttk.Scrollbar(history_tree_frame)
        history_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.history_tree = ttk.Treeview(history_tree_frame, 
                                         columns=("timestamp", "file", "size", "client", "status"),
                                         show="headings", 
                                         yscrollcommand=history_scroll.set)
        self.history_tree.heading("timestamp", text="Timestamp")
        self.history_tree.heading("file", text="File")
        self.history_tree.heading("size", text="Size")
        self.history_tree.heading("client", text="Client")
        self.history_tree.heading("status", text="Status")
        
        self.history_tree.column("timestamp", width=140)
        self.history_tree.column("file", width=150)
        self.history_tree.column("size", width=80)
        self.history_tree.column("client", width=150)
        self.history_tree.column("status", width=100)
        
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        history_scroll.config(command=self.history_tree.yview)
        
        # Logs tab
        self.logs_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.logs_frame, text="Server Logs")
        
        # Create log text area
        log_frame = ttk.Frame(self.logs_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_scroll_y = ttk.Scrollbar(log_frame)
        log_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        log_scroll_x = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL)
        log_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.log_text = tk.Text(log_frame, wrap=tk.NONE, height=10,
                               yscrollcommand=log_scroll_y.set,
                               xscrollcommand=log_scroll_x.set)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        log_scroll_y.config(command=self.log_text.yview)
        log_scroll_x.config(command=self.log_text.xview)
        
        # Status bar at the bottom
        self.status_bar = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def toggle_server(self):
        """Start or stop the server"""
        if not self.server_running:
            # Start the server
            try:
                host = self.host_var.get()
                port = int(self.port_var.get())
                
                # Validate port number
                if port < 1024 or port > 65535:
                    messagebox.showerror("Invalid Port", "Port must be between 1024 and 65535")
                    return
                
                success = self.file_server.start(host, port, self.on_client_connected)
                
                if success:
                    self.server_running = True
                    self.server_status.set(f"Server Running on {host}:{port}")
                    self.start_button.config(text="Stop Server")
                    self.select_button.config(state=tk.NORMAL)
                    self.update_status(f"Server started on {host}:{port}")
                    self.add_log(f"Server started on {host}:{port}")
                else:
                    messagebox.showerror("Server Error", "Failed to start server")
            except ValueError:
                messagebox.showerror("Invalid Port", "Port must be a number")
        else:
            # Stop the server
            self.file_server.stop()
            self.server_running = False
            self.server_status.set("Server Stopped")
            self.start_button.config(text="Start Server")
            self.select_button.config(state=tk.DISABLED)
            self.update_status("Server stopped")
            self.add_log("Server stopped")
    
    def select_file(self):
        """Open file dialog to select a file to serve"""
        file_path = filedialog.askopenfilename()
        if file_path:
            self.selected_file.set(file_path)
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            size_display = self.format_size(file_size)
            
            self.file_label.config(text=f"{file_name} ({size_display})")
            self.update_status(f"Selected file: {file_name}")
            self.add_log(f"File selected: {file_path}")
            
            # Handle new clients with this file
            for client_socket in self.file_server.connected_clients:
                self.handle_client(client_socket, file_path)
    
    def handle_client(self, client_socket, file_path):
        """Handle a client connection with file transfer"""
        # Create progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("File Transfer Progress")
        progress_window.geometry("300x120")
        progress_window.resizable(False, False)
        progress_window.transient(self.root)
        
        # Add progress bar and labels
        ttk.Label(progress_window, text=f"Sending: {os.path.basename(file_path)}").pack(pady=10)
        
        progress_var = tk.IntVar(value=0)
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        status_var = tk.StringVar(value="Starting transfer...")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
        
        def update_progress(value):
            progress_var.set(value)
            status_var.set(f"Transferring: {value}%")
            progress_window.update_idletasks()
        
        # Start file transfer in a separate thread
        threading.Thread(
            target=self._file_transfer_thread,
            args=(client_socket, file_path, progress_window, update_progress, status_var),
            daemon=True
        ).start()
    
    def _file_transfer_thread(self, client_socket, file_path, progress_window, update_progress, status_var):
        """Thread function to handle file transfer"""
        success = self.file_server.send_file(client_socket, file_path, update_progress)
        
        if success:
            status_var.set("Transfer complete!")
        else:
            status_var.set("Transfer failed!")
        
        # Update the history view
        self.root.after(100, self.update_history_view)
        
        # Close progress window after a delay
        self.root.after(1500, progress_window.destroy)
    
    def on_client_connected(self, client_info):
        """Callback when a new client connects"""
        self.add_log(f"Client connected: {client_info}")
        
        # Add to the client tree view
        self.client_tree.insert("", tk.END, values=(client_info, "Connected"))
        
        # Update status
        self.update_status(f"Client connected: {client_info}")
        
        # If a file is already selected, start transfer
        file_path = self.selected_file.get()
        if file_path:
            # Find the client socket that corresponds to this client info
            for client_socket in self.file_server.connected_clients:
                sock_info = f"{client_socket.getpeername()[0]}:{client_socket.getpeername()[1]}"
                if sock_info == client_info:
                    self.handle_client(client_socket, file_path)
                    break
    
    def update_history_view(self):
        """Update the transfer history view"""
        # Clear existing entries
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # Add history items
        for record in self.file_server.transfer_history:
            size_display = self.format_size(record["size"])
            self.history_tree.insert("", tk.END, values=(
                record["timestamp"],
                record["file"],
                size_display,
                record["client"],
                record["status"]
            ))
    
    def add_log(self, message):
        """Add a log message to the log text area"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)  # Scroll to bottom
    
    def update_status(self, message):
        """Update the status bar message"""
        self.status_bar.config(text=message)
    
    def format_size(self, size_bytes):
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024 or unit == 'GB':
                if unit == 'B':
                    return f"{size_bytes} {unit}"
                return f"{size_bytes/1024:.2f} {unit}"
            size_bytes /= 1024
    
    def on_close(self):
        """Handle window close event"""
        if self.server_running:
            if messagebox.askyesno("Quit", "Server is running. Do you want to stop it and quit?"):
                self.file_server.stop()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    # Set up app theming
    root = tk.Tk()
    root.tk.call('tk', 'scaling', 1.3)  # Adjust scaling for high DPI displays
    
    # Create and start the application
    app = ServerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()