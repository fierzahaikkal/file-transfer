import socket
import threading
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import logging
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("client_log.txt"), logging.StreamHandler()]
)

# Default server settings
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 12345
BUFFER_SIZE = 4096

class FileClient:
    def __init__(self):
        self.socket = None
        self.connected = False
        self.download_history = []
    
    def connect(self, host, port):
        """Connect to the file server"""
        if self.connected:
            return False
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.connected = True
            logging.info(f"Connected to server at {host}:{port}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the server"""
        if not self.connected:
            return
        
        try:
            if self.socket:
                self.socket.close()
            self.connected = False
            logging.info("Disconnected from server")
        except Exception as e:
            logging.error(f"Error during disconnect: {str(e)}")
    
    def receive_file(self, save_path, progress_callback=None):
        """Receive a file from the server with retry mechanism"""
        if not self.connected:
            raise ConnectionError("Not connected to server")
        
        MAX_RETRIES = 3
        RETRY_DELAY = 2  # seconds
        last_exception = None
        
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    # Reconnect if this is a retry attempt
                    if not self.connect(self.socket.getsockname()[0], self.socket.getsockname()[1]):
                        continue
                
                # First, receive the file header (name and size)
                header_data = b""
                while b'\n' not in header_data:
                    try:
                        chunk = self.socket.recv(BUFFER_SIZE)
                        if not chunk:
                            raise ConnectionError("Connection closed before receiving file header")
                        header_data += chunk
                        if len(header_data) > 1024000:  # Prevent excessive header size
                            raise ValueError("File header too large, possibly invalid data")
                    except socket.error as e:
                        if attempt < MAX_RETRIES - 1:
                            raise e
                        else:
                            last_exception = e
                            break
                
                header_end = header_data.find(b'\n')
                header = header_data[:header_end].decode()
                remaining_data = header_data[header_end + 1:]
                
                # Parse the header
                try:
                    file_name, file_size, file_extension = header.split('|')
                    file_size = int(file_size)
                except ValueError:
                    raise ValueError("Invalid file header format")
                
                # Append file extension to save path if not manually specified
                if os.path.splitext(save_path)[1] == '':
                    save_path = save_path + file_extension
                
                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
                
                # Start receiving the file
                received_bytes = len(remaining_data)
                last_progress_update = time.time()
                
                # Open file in append mode if this is a retry and file exists
                file_mode = 'ab' if attempt > 0 and os.path.exists(save_path) else 'wb'
                
                with open(save_path, file_mode) as file:
                    # Write any data we already received after the header
                    if remaining_data and file_mode == 'wb':
                        file.write(remaining_data)
                    
                    # Continue receiving data
                    while received_bytes < file_size:
                        try:
                            chunk = self.socket.recv(min(BUFFER_SIZE, file_size - received_bytes))
                            if not chunk:
                                if attempt < MAX_RETRIES - 1:
                                    raise ConnectionError("Connection lost during transfer")
                                break
                            
                            file.write(chunk)
                            received_bytes += len(chunk)
                            
                            # Update progress
                            current_time = time.time()
                            if progress_callback and (current_time - last_progress_update) > 0.1:
                                progress = int((received_bytes / file_size) * 100)
                                progress_callback(progress, received_bytes, file_size)
                                last_progress_update = current_time
                        except socket.error as e:
                            if attempt < MAX_RETRIES - 1:
                                last_exception = e
                                logging.warning(f"Transfer interrupted, retrying in {RETRY_DELAY} seconds...")
                                time.sleep(RETRY_DELAY)
                                break
                            else:
                                raise e
                    
                    if received_bytes >= file_size:
                        # Transfer completed successfully
                        if progress_callback:
                            progress_callback(100, received_bytes, file_size)
                        
                        # Record the download
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        download_record = {
                            "timestamp": timestamp,
                            "file_name": os.path.basename(save_path),
                            "original_name": file_name,
                            "size": file_size,
                            "path": save_path,
                            "status": "Complete"
                        }
                        self.download_history.append(download_record)
                        logging.info(f"File received and saved as '{save_path}'")
                        return True
            
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    logging.warning(f"Attempt {attempt + 1} failed, retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    raise e
        
        # If we get here, all retries failed
        if last_exception:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            download_record = {
                "timestamp": timestamp,
                "file_name": os.path.basename(save_path) if save_path else "unknown",
                "original_name": "unknown",
                "size": 0,
                "path": save_path if save_path else "unknown",
                "status": f"Failed: {str(last_exception)}"
            }
            self.download_history.append(download_record)
            logging.error(f"Error receiving file: {str(last_exception)}")
            raise last_exception
        
        return False


class ClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced File Transfer Client")
        self.root.geometry("750x550")
        self.root.minsize(550, 450)
        
        # Initialize file client
        self.file_client = FileClient()
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')  # Modern looking theme
        
        # Configure colors
        bg_color = "#f5f5f5"
        accent_color = "#1976d2"
        
        self.style.configure("TButton", padding=6, font=("Segoe UI", 10))
        self.style.configure("TLabel", font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        self.style.configure("Status.TLabel", font=("Segoe UI", 9))
        self.style.configure("Success.TLabel", foreground="green", font=("Segoe UI", 10))
        self.style.configure("Error.TLabel", foreground="red", font=("Segoe UI", 10))
        
        self.root.configure(bg=bg_color)
        
        # Variables
        self.server_host = tk.StringVar(value=DEFAULT_HOST)
        self.server_port = tk.StringVar(value=str(DEFAULT_PORT))
        self.connection_status = tk.StringVar(value="Disconnected")
        self.save_directory = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.auto_connect = tk.BooleanVar(value=False)
        self.auto_save = tk.BooleanVar(value=True)
        
        # Create main layout
        self.create_main_layout()
        
        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Auto-connect if option is set
        if self.auto_connect.get():
            self.toggle_connect()
    
    def create_main_layout(self):
        """Create the main application layout"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create paned window for resizable sections
        paned_window = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned_window.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Top section - Connection settings
        top_frame = ttk.LabelFrame(paned_window, text="Connection Settings", padding="10")
        paned_window.add(top_frame, weight=1)
        
        # Server connection frame
        conn_frame = ttk.Frame(top_frame)
        conn_frame.pack(fill=tk.X, pady=5)
        
        # Connection settings
        ttk.Label(conn_frame, text="Server Host:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(conn_frame, textvariable=self.server_host, width=15).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(conn_frame, textvariable=self.server_port, width=6).grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)
        
        # Save directory
        save_dir_frame = ttk.Frame(top_frame)
        save_dir_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(save_dir_frame, text="Save Location:").pack(side=tk.LEFT, padx=5)
        
        save_entry = ttk.Entry(save_dir_frame, textvariable=self.save_directory, width=45)
        save_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(save_dir_frame, text="Browse...", command=self.browse_save_location)
        browse_btn.pack(side=tk.LEFT, padx=5)
        
        # Options frame
        options_frame = ttk.Frame(top_frame)
        options_frame.pack(fill=tk.X, pady=5)
        
        auto_connect_check = ttk.Checkbutton(options_frame, text="Auto-connect on startup", 
                                             variable=self.auto_connect)
        auto_connect_check.pack(side=tk.LEFT, padx=5)
        
        auto_save_check = ttk.Checkbutton(options_frame, text="Auto-generate filenames", 
                                          variable=self.auto_save)
        auto_save_check.pack(side=tk.LEFT, padx=20)
        
        # Control buttons
        control_frame = ttk.Frame(top_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        self.connect_button = ttk.Button(control_frame, text="Connect", command=self.toggle_connect)
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        self.receive_button = ttk.Button(control_frame, text="Receive File", command=self.receive_file)
        self.receive_button.pack(side=tk.LEFT, padx=5)
        self.receive_button.config(state=tk.DISABLED)
        
        # Status section
        status_frame = ttk.Frame(top_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, padx=5, sticky=tk.W)
        
        self.status_label = ttk.Label(status_frame, textvariable=self.connection_status)
        self.status_label.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(paned_window)
        paned_window.add(notebook, weight=3)
        
        # Downloads tab
        self.downloads_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.downloads_frame, text="Download History")
        
        # Create download history tree view
        downloads_tree_frame = ttk.Frame(self.downloads_frame)
        downloads_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        download_scroll = ttk.Scrollbar(downloads_tree_frame)
        download_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.downloads_tree = ttk.Treeview(downloads_tree_frame, 
                                         columns=("timestamp", "filename", "size", "path", "status"),
                                         show="headings", 
                                         yscrollcommand=download_scroll.set)
        
        self.downloads_tree.heading("timestamp", text="Timestamp")
        self.downloads_tree.heading("filename", text="Filename")
        self.downloads_tree.heading("size", text="Size")
        self.downloads_tree.heading("path", text="Path")
        self.downloads_tree.heading("status", text="Status")
        
        self.downloads_tree.column("timestamp", width=140)
        self.downloads_tree.column("filename", width=150)
        self.downloads_tree.column("size", width=80)
        self.downloads_tree.column("path", width=200)
        self.downloads_tree.column("status", width=100)
        
        self.downloads_tree.pack(fill=tk.BOTH, expand=True)
        download_scroll.config(command=self.downloads_tree.yview)
        
        # Right-click menu for download history
        self.download_menu = tk.Menu(self.root, tearoff=0)
        self.download_menu.add_command(label="Open File", command=self.open_selected_file)
        self.download_menu.add_command(label="Open Containing Folder", command=self.open_file_location)
        self.download_menu.add_separator()
        self.download_menu.add_command(label="Copy Path", command=self.copy_file_path)
        
        self.downloads_tree.bind("<Button-3>", self.show_download_menu)
        self.downloads_tree.bind("<Double-1>", self.on_download_double_click)
        
        # Logs tab
        self.logs_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.logs_frame, text="Client Logs")
        
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
        
        # Add clear buttons for logs and history
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        clear_logs_btn = ttk.Button(buttons_frame, text="Clear Logs", 
                                   command=lambda: self.log_text.delete(1.0, tk.END))
        clear_logs_btn.pack(side=tk.RIGHT, padx=5)
        
        clear_history_btn = ttk.Button(buttons_frame, text="Clear History", 
                                      command=self.clear_download_history)
        clear_history_btn.pack(side=tk.RIGHT, padx=5)
    
    def toggle_connect(self):
        """Connect to or disconnect from the server"""
        if not self.file_client.connected:
            # Connect to the server
            try:
                host = self.server_host.get()
                port = int(self.server_port.get())
                
                # Validate port number
                if port < 1 or port > 65535:
                    messagebox.showerror("Invalid Port", "Port must be between 1 and 65535")
                    return
                
                success = self.file_client.connect(host, port)
                
                if success:
                    self.connection_status.set(f"Connected to {host}:{port}")
                    self.status_label.config(style="Success.TLabel")
                    self.connect_button.config(text="Disconnect")
                    self.receive_button.config(state=tk.NORMAL)
                    self.update_status(f"Connected to server at {host}:{port}")
                    self.add_log(f"Connected to server at {host}:{port}")
                else:
                    self.connection_status.set("Connection failed")
                    self.status_label.config(style="Error.TLabel")
                    self.add_log(f"Failed to connect to {host}:{port}")
                    messagebox.showerror("Connection Error", f"Failed to connect to {host}:{port}")
            except ValueError:
                messagebox.showerror("Invalid Port", "Port must be a number")
        else:
            # Disconnect from the server
            self.file_client.disconnect()
            self.connection_status.set("Disconnected")
            self.status_label.config(style="")
            self.connect_button.config(text="Connect")
            self.receive_button.config(state=tk.DISABLED)
            self.add_log("Disconnected from server")
            self.update_status("Disconnected from server")
    
    def browse_save_location(self):
        """Open dialog to select save directory"""
        directory = filedialog.askdirectory(initialdir=self.save_directory.get())
        if directory:
            self.save_directory.set(directory)
            self.add_log(f"Save location changed to {directory}")
    
    def receive_file(self):
        """Receive a file from the server"""
        if not self.file_client.connected:
            messagebox.showerror("Error", "Not connected to a server")
            return
        
        # Determine save path
        if self.auto_save.get():
            # Auto-generate filename with timestamp and extension
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(self.save_directory.get(), f"received_file_{timestamp}")
            # Wait for server to send file extension
            # Extension will be appended after receiving the header
        else:
            # Ask user for save location
            save_path = filedialog.asksaveasfilename(
                initialdir=self.save_directory.get(),
                title="Save Received File As",
                filetypes=[("All files", "*.*")]
            )
            
        if not save_path:
            self.add_log("File receive cancelled - no save path specified")
            return
        
        # Create progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Receiving File")
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)
        progress_window.transient(self.root)
        progress_window.grab_set()  # Modal dialog
        
        # Add progress indicators
        ttk.Label(progress_window, text="Receiving file from server...", font=("Segoe UI", 10)).pack(pady=10)
        
        progress_var = tk.IntVar(value=0)
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=350)
        progress_bar.pack(padx=10, pady=5)
        
        progress_text = tk.StringVar(value="Starting download...")
        progress_label = ttk.Label(progress_window, textvariable=progress_text, font=("Segoe UI", 9))
        progress_label.pack(pady=5)
        
        size_var = tk.StringVar(value="Received: 0 B / 0 B")
        size_label = ttk.Label(progress_window, textvariable=size_var, font=("Segoe UI", 9))
        size_label.pack(pady=5)
        
        cancel_button = ttk.Button(progress_window, text="Cancel", 
                                  command=lambda: progress_window.destroy())
        cancel_button.pack(pady=5)
        
        def progress_callback(percent, received, total):
            progress_var.set(percent)
            progress_text.set(f"Downloading: {percent}%")
            size_var.set(f"Received: {self.format_size(received)} / {self.format_size(total)}")
            
            if percent >= 100:
                progress_text.set("Download complete!")
                cancel_button.config(text="Close")
        
        # Start file transfer in a separate thread
        threading.Thread(
            target=self._receive_file_thread,
            args=(save_path, progress_callback, progress_window),
            daemon=True
        ).start()
    
    def _receive_file_thread(self, save_path, progress_callback, progress_window):
        """Thread function to handle file receiving"""
        try:
            success = self.file_client.receive_file(save_path, progress_callback)
            
            if success:
                self.update_status(f"File received and saved successfully")
                self.add_log(f"File received and saved as: {save_path}")
                
                # Update the download history view
                self.root.after(100, self.update_download_history)
            
        except Exception as e:
            error_msg = f"Error receiving file: {str(e)}"
            self.add_log(error_msg)
            self.update_status(error_msg)
            
            # Update the progress window
            self.root.after(0, lambda: messagebox.showerror("Download Error", error_msg, parent=progress_window))
            
            # Update the download history view
            self.root.after(100, self.update_download_history)
    
    def update_download_history(self):
        """Update the download history treeview"""
        # Clear existing entries
        for item in self.downloads_tree.get_children():
            self.downloads_tree.delete(item)
        
        # Add history items
        for record in self.file_client.download_history:
            size_display = self.format_size(record.get("size", 0))
            status = record.get("status", "Unknown")
            
            # Apply status-specific tags for coloring
            tags = ("success",) if "Complete" in status else ("error",)
            
            self.downloads_tree.insert("", tk.END, values=(
                record.get("timestamp", ""),
                record.get("file_name", ""),
                size_display,
                record.get("path", ""),
                status
            ), tags=tags)
        
        # Configure tag colors
        self.downloads_tree.tag_configure("success", foreground="green")
        self.downloads_tree.tag_configure("error", foreground="red")
    
    def clear_download_history(self):
        """Clear the download history"""
        if messagebox.askyesno("Clear History", "Are you sure you want to clear the download history?"):
            self.file_client.download_history = []
            self.update_download_history()
            self.add_log("Download history cleared")
    
    def show_download_menu(self, event):
        """Show context menu for download entries"""
        # Check if there's a selection
        selection = self.downloads_tree.selection()
        if selection:
            self.downloads_tree.identify_row(event.y)
            self.download_menu.post(event.x_root, event.y_root)
    
    def open_selected_file(self):
        """Open the selected file"""
        selection = self.downloads_tree.selection()
        if not selection:
            return
        
        item = self.downloads_tree.item(selection[0])
        file_path = item["values"][3]  # Path is in the 4th column
        
        if os.path.exists(file_path):
            self.add_log(f"Opening file: {file_path}")
            
            # Use appropriate platform-specific command to open file
            import subprocess
            import platform
            
            system = platform.system()
            try:
                if system == 'Windows':
                    os.startfile(file_path)
                elif system == 'Darwin':  # macOS
                    subprocess.call(('open', file_path))
                else:  # Linux and others
                    subprocess.call(('xdg-open', file_path))
            except Exception as e:
                self.add_log(f"Error opening file: {str(e)}")
                messagebox.showerror("Error", f"Could not open file: {str(e)}")
        else:
            self.add_log(f"File not found: {file_path}")
            messagebox.showerror("Error", "File does not exist")
    
    def open_file_location(self):
        """Open the folder containing the selected file"""
        selection = self.downloads_tree.selection()
        if not selection:
            return
        
        item = self.downloads_tree.item(selection[0])
        file_path = item["values"][3]  # Path is in the 4th column
        
        if os.path.exists(file_path):
            folder_path = os.path.dirname(file_path)
            self.add_log(f"Opening folder: {folder_path}")
            
            # Use appropriate platform-specific command
            import subprocess
            import platform
            
            system = platform.system()
            try:
                if system == 'Windows':
                    subprocess.call(f'explorer /select,"{file_path}"', shell=True)
                elif system == 'Darwin':  # macOS
                    subprocess.call(['open', folder_path])
                else:  # Linux and others
                    subprocess.call(['xdg-open', folder_path])
            except Exception as e:
                self.add_log(f"Error opening folder: {str(e)}")
                messagebox.showerror("Error", f"Could not open folder: {str(e)}")
        else:
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir):
                self.add_log(f"File not found, opening parent folder: {parent_dir}")
                
                # Use appropriate platform-specific command
                import subprocess
                import platform
                
                system = platform.system()
                try:
                    if system == 'Windows':
                        os.startfile(parent_dir)
                    elif system == 'Darwin':  # macOS
                        subprocess.call(['open', parent_dir])
                    else:  # Linux and others
                        subprocess.call(['xdg-open', parent_dir])
                except Exception as e:
                    self.add_log(f"Error opening folder: {str(e)}")
                    messagebox.showerror("Error", f"Could not open folder: {str(e)}")
            else:
                self.add_log(f"Folder not found: {parent_dir}")
                messagebox.showerror("Error", "Folder does not exist")
    
    def copy_file_path(self):
        """Copy the selected file path to clipboard"""
        selection = self.downloads_tree.selection()
        if not selection:
            return
        
        item = self.downloads_tree.item(selection[0])
        file_path = item["values"][3]  # Path is in the 4th column
        
        self.root.clipboard_clear()
        self.root.clipboard_append(file_path)
        self.add_log(f"Copied path to clipboard: {file_path}")
        self.update_status("File path copied to clipboard")
    
    def on_download_double_click(self, event):
        """Handle double-click on download entry"""
        self.open_selected_file()
    
    def add_log(self, message):
        """Add a message to the log"""
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
            if size_bytes < 1024000 or unit == 'GB':
                if unit == 'B':
                    return f"{size_bytes} {unit}"
                return f"{size_bytes/1024000:.2f} {unit}"
            size_bytes /= 1024000
        return "0 B"  # Default for zero or invalid size
    
    def on_close(self):
        """Handle window close event"""
        if self.file_client.connected:
            if messagebox.askyesno("Quit", "Currently connected to server. Disconnect and quit?"):
                self.file_client.disconnect()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    # Set up app theming
    root = tk.Tk()
    root.tk.call('tk', 'scaling', 1.3)  # Adjust scaling for high DPI displays
    
    # Create and start the application
    app = ClientGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()