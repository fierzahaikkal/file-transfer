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
        """Receive a file from the server"""
        if not self.connected:
            raise ConnectionError("Not connected to server")
        
        try:
            # First, receive the file header
            header_data = b""
            while b'\n' not in header_data:
                chunk = self.socket.recv(BUFFER_SIZE)
                if not chunk:
                    raise ConnectionError("Connection closed before receiving file header")
                header_data += chunk
            
            header_end = header_data.find(b'\n')
            header = header_data[:header_end].decode()
            remaining_data = header_data[header_end + 1:]
            
            # Parse the header
            file_name, file_size = header.split('|')
            file_size = int(file_size)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
            
            # Start receiving the file
            received_bytes = len(remaining_data)
            last_progress_update = time.time()
            
            with open(save_path, 'wb') as file:
                if remaining_data:
                    file.write(remaining_data)
                
                while received_bytes < file_size:
                    chunk = self.socket.recv(min(BUFFER_SIZE, file_size - received_bytes))
                    if not chunk:
                        break
                    
                    file.write(chunk)
                    received_bytes += len(chunk)
                    
                    if progress_callback and (time.time() - last_progress_update) > 0.1:
                        progress = int((received_bytes / file_size) * 100)
                        progress_callback(progress, received_bytes, file_size)
                        last_progress_update = time.time()
            
            if progress_callback:
                progress_callback(100, received_bytes, file_size)
            
            # Record download
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            download_record = {
                "timestamp": timestamp,
                "file_name": os.path.basename(save_path),
                "original_name": file_name,
                "size": file_size,
                "path": save_path,
                "status": "Complete" if received_bytes >= file_size else f"Incomplete ({received_bytes}/{file_size} bytes)"
            }
            self.download_history.append(download_record)
            
            logging.info(f"File received and saved as '{save_path}'")
            return True
            
        except Exception as e:
            logging.error(f"Error receiving file: {str(e)}")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            download_record = {
                "timestamp": timestamp,
                "file_name": os.path.basename(save_path) if save_path else "unknown",
                "original_name": "unknown",
                "size": 0,
                "path": save_path if save_path else "unknown",
                "status": f"Failed: {str(e)}"
            }
            self.download_history.append(download_record)
            raise e

class ClientUI:
    def __init__(self):
        self.file_client = FileClient()
        self.save_directory = os.path.join(os.path.expanduser("~"), "Downloads")
        self.auto_connect = False
        self.auto_save = True

    def main_page(self, page: ft.Page):
        page.title = "Modern File Transfer Client"
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

        # Connection controls
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

        self.connect_button = ft.ElevatedButton(
            text="Connect",
            icon=ft.Icons.LINK,
            on_click=self.toggle_connect
        )

        # Status indicator
        self.status_text = ft.Text(
            value="Disconnected",
            color=ft.Colors.RED_400,
            size=14
        )

        # Progress indicator
        self.progress_bar = ft.ProgressBar(
            width=400,
            height=20,
            visible=False
        )

        self.progress_text = ft.Text(
            size=14,
            visible=False
        )

        # History data table
        self.history_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Timestamp")),
                ft.DataColumn(ft.Text("File Name")),
                ft.DataColumn(ft.Text("Size")),
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
                                    self.connect_button
                                ], alignment=ft.MainAxisAlignment.START),
                                ft.Row([self.status_text])
                            ]),
                            padding=20
                        )
                    ),
                    ft.Container(height=20),
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text("Transfer Progress", size=16, weight=ft.FontWeight.BOLD),
                                self.progress_bar,
                                self.progress_text
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

    def toggle_connect(self, e):
        if not self.file_client.connected:
            try:
                host = self.host_field.value
                port = int(self.port_field.value)
                
                if self.file_client.connect(host, port):
                    self.connect_button.text = "Disconnect"
                    self.connect_button.icon = ft.Icons.LINK_OFF
                    self.status_text.value = "Connected"
                    self.status_text.color = ft.Colors.GREEN_400
                else:
                    ft.Banner(
                        bgcolor=ft.Colors.RED_100,
                        leading=ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=40),
                        content=ft.Text("Failed to connect to server")
                    ).open = True
            except ValueError:
                ft.Banner(
                    bgcolor=ft.Colors.RED_100,
                    leading=ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=40),
                    content=ft.Text("Invalid port number")
                ).open = True
        else:
            self.file_client.disconnect()
            self.connect_button.text = "Connect"
            self.connect_button.icon = ft.Icons.LINK
            self.status_text.value = "Disconnected"
            self.status_text.color = ft.Colors.RED_400

        self.connect_button.update()
        self.status_text.update()

    def update_progress(self, progress, received_bytes, total_bytes):
        def update(e):
            self.progress_bar.value = progress / 100
            self.progress_text.value = f"Received: {received_bytes}/{total_bytes} bytes ({progress}%)"
            self.progress_bar.update()
            self.progress_text.update()

        self.progress_bar.visible = True
        self.progress_text.visible = True
        update(None)

    def update_history(self):
        self.history_table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(record["timestamp"])),
                    ft.DataCell(ft.Text(record["file_name"])),
                    ft.DataCell(ft.Text(f"{record['size']} bytes")),
                    ft.DataCell(ft.Text(record["status"]))
                ]
            ) for record in self.file_client.download_history
        ]
        self.history_table.update()

def main(page: ft.Page):
    client_ui = ClientUI()
    client_ui.main_page(page)

if __name__ == "__main__":
    ft.app(target=main)