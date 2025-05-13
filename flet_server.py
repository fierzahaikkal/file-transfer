import flet as ft
import socket
import threading
import os
from datetime import datetime
import logging
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("server_log.txt"), logging.StreamHandler()]
)

# Default server settings
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 12345
BUFFER_SIZE = 4096

class FileServer:
    def __init__(self):
        self.server_socket = None
        self.running = False
        self.clients = []
        self.selected_file = None
        self.transfer_history = []
        self.client_threads = []
    
    def start(self, host, port):
        """Start the file server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((host, port))
            self.server_socket.listen(5)
            self.running = True
            logging.info(f"Server started on {host}:{port}")
            return True
        except Exception as e:
            logging.error(f"Failed to start server: {str(e)}")
            return False
    
    def stop(self):
        """Stop the file server"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        self.clients = []
        logging.info("Server stopped")
    
    def accept_clients(self, on_client_connected):
        """Accept incoming client connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                self.clients.append(client_socket)
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address, on_client_connected),
                    daemon=True
                )
                self.client_threads.append(client_thread)
                client_thread.start()
            except:
                if self.running:
                    logging.error("Error accepting client connection")
                break
    
    def _handle_client(self, client_socket, address, on_client_connected):
        """Handle individual client connection"""
        client_info = f"{address[0]}:{address[1]}"
        logging.info(f"New client connected: {client_info}")
        on_client_connected(client_info)
        
        try:
            while self.running:
                if self.selected_file and os.path.exists(self.selected_file):
                    self._send_file(client_socket, self.selected_file, client_info)
                    break
                time.sleep(0.1)
        except:
            pass
        finally:
            if client_socket in self.clients:
                self.clients.remove(client_socket)
            try:
                client_socket.close()
            except:
                pass
            logging.info(f"Client disconnected: {client_info}")
    
    def _send_file(self, client_socket, file_path, client_info):
        """Send file to client"""
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            # Send file header
            header = f"{file_name}|{file_size}\n"
            client_socket.send(header.encode())
            
            # Send file data
            sent_bytes = 0
            with open(file_path, 'rb') as file:
                while sent_bytes < file_size:
                    chunk = file.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    client_socket.send(chunk)
                    sent_bytes += len(chunk)
            
            # Record transfer
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            transfer_record = {
                "timestamp": timestamp,
                "file_name": file_name,
                "size": file_size,
                "client": client_info,
                "status": "Complete" if sent_bytes >= file_size else f"Incomplete ({sent_bytes}/{file_size} bytes)"
            }
            self.transfer_history.append(transfer_record)
            
            logging.info(f"File sent to {client_info}: {file_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error sending file to {client_info}: {str(e)}")
            
            # Record failed transfer
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            transfer_record = {
                "timestamp": timestamp,
                "file_name": os.path.basename(file_path) if file_path else "unknown",
                "size": 0,
                "client": client_info,
                "status": f"Failed: {str(e)}"
            }
            self.transfer_history.append(transfer_record)
            return False

class ServerUI:
    def __init__(self):
        self.file_server = FileServer()
        self.accept_thread = None
    
    def main_page(self, page: ft.Page):
        page.title = "Modern File Transfer Server"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 20
        page.window_width = 800
        page.window_height = 600
        page.window_min_width = 600
        page.window_min_height = 500

        # Theme colors
        page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary="#FFFFFF",
                primary_container="#5186ED",
                secondary="#5186ED"
            )
        )

        # Server controls
        self.host_field = ft.TextField(
            label="Host",
            value=DEFAULT_HOST,
            width=200,
            text_size=14
        )

        self.port_field = ft.TextField(
            label="Port",
            value=str(DEFAULT_PORT),
            width=100,
            text_size=14
        )

        self.start_button = ft.ElevatedButton(
            text="Start Server",
            on_click=self.toggle_server
        )

        self.select_button = ft.ElevatedButton(
            text="Select File",
            disabled=True,
            on_click=self.select_file
        )

        # Status indicator
        self.status_text = ft.Text(
            value="Server Stopped",
            color=ft.Colors.RED_400,
            size=14
        )

        # Selected file display
        self.file_text = ft.Text(
            value="No file selected",
            size=14,
            color=ft.Colors.GREY_700
        )

        # Connected clients list
        self.clients_list = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Client")),
                ft.DataColumn(ft.Text("Status"))
            ],
            rows=[]
        )

        # Transfer history table
        self.history_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Timestamp")),
                ft.DataColumn(ft.Text("File")),
                ft.DataColumn(ft.Text("Size")),
                ft.DataColumn(ft.Text("Client")),
                ft.DataColumn(ft.Text("Status"))
            ],
            rows=[]
        )

        # Layout
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    self.host_field,
                                    self.port_field,
                                    self.start_button,
                                    self.select_button
                                ], alignment=ft.MainAxisAlignment.START),
                                ft.Row([self.status_text]),
                                ft.Row([self.file_text])
                            ]),
                            padding=20
                        )
                    ),
                    ft.Container(height=20),
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text("Connected Clients", size=16, weight=ft.FontWeight.BOLD),
                                ft.Container(height=10),
                                self.clients_list
                            ]),
                            padding=20
                        )
                    ),
                    ft.Container(height=20),
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text("Transfer History", size=16, weight=ft.FontWeight.BOLD),
                                ft.Container(height=10),
                                self.history_table
                            ]),
                            padding=20
                        )
                    )
                ])
            )
        )

    def toggle_server(self, e):
        if not self.file_server.running:
            try:
                host = self.host_field.value
                port = int(self.port_field.value)
                
                if self.file_server.start(host, port):
                    self.start_button.text = "Stop Server"
                    self.start_button.icon = ft.Icons.STOP_CIRCLE
                    self.status_text.value = "Server Running"
                    self.status_text.color = ft.Colors.GREEN_400
                    self.select_button.disabled = False
                    
                    self.accept_thread = threading.Thread(
                        target=self.file_server.accept_clients,
                        args=(self.on_client_connected,),
                        daemon=True
                    )
                    self.accept_thread.start()
                else:
                    ft.Banner(
                        bgcolor=ft.Colors.RED_100,
                        leading=ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=40),
                        content=ft.Text("Failed to start server")
                    ).open = True
            except ValueError:
                ft.Banner(
                    bgcolor=ft.Colors.RED_100,
                    leading=ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=40),
                    content=ft.Text("Invalid port number")
                ).open = True
        else:
            self.file_server.stop()
            self.start_button.text = "Start Server"
            self.start_button.icon = ft.Icons.PLAY_CIRCLE_ROUNDED
            self.status_text.value = "Server Stopped"
            self.status_text.color = ft.Colors.RED_400
            self.select_button.disabled = True
            self.file_text.value = "No file selected"
            self.file_server.selected_file = None
            self.clients_list.rows = []

        self.start_button.update()
        self.status_text.update()
        self.select_button.update()
        self.file_text.update()
        self.clients_list.update()

    def select_file(self, e):
        def pick_files_result(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                file_path = e.files[0].path
                self.file_server.selected_file = file_path
                self.file_text.value = f"Selected: {os.path.basename(file_path)}"
                self.file_text.update()

        pick_files_dialog = ft.FilePicker(
            on_result=pick_files_result
        )
        self.page.overlay.append(pick_files_dialog)
        pick_files_dialog.pick_files()

    def on_client_connected(self, client_info):
        def update_ui():
            self.clients_list.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(client_info)),
                        ft.DataCell(ft.Text("Connected"))
                    ]
                )
            )
            self.clients_list.update()

        self.page.update_async(update_ui)

def main(page: ft.Page):
    server_ui = ServerUI()
    server_ui.main_page(page)

if __name__ == "__main__":
    ft.app(target=main)