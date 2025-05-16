# SwiftShare

A simple and intuitive application for sharing files between computers on your network. With a modern graphical interface and real-time progress tracking, sending files has never been easier!

## Features

- **User-Friendly Interface**: Clean and modern design that makes file sharing straightforward
- **Real-Time Progress**: Watch your file transfers in real-time with a progress bar
- **Transfer History**: Keep track of all your file transfers, including successful and failed attempts
- **Multiple Connections**: Connect with multiple clients simultaneously
- **Server Logs**: Monitor all server activities through the built-in logging system

## Getting Started

### Prerequisites

Before you begin, ensure you have Python 3.x installed on your computer. You can download it from [python.org](https://python.org).

### Installation

1. Download or clone this repository to your computer
2. Open a terminal/command prompt in the project folder
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Starting the Server

1. Run the server application:
   ```
   python file_server_new.py
   ```
2. The server interface will appear
3. Click "Start Server" to begin accepting connections
4. Select a file to share when clients connect

### Connecting as a Client

1. Run the client application:
   ```
   python file_client_new.py
   ```
2. Enter the server's IP address and port
3. Wait to receive files from the server

## Tips for Best Use

- Keep the server application running as long as you need to share files
- Monitor transfer progress through the progress bar
- Check the transfer history tab to verify successful transfers
- Use the logs tab to troubleshoot any issues

## Need Help?

If you encounter any issues:

1. Check that both server and client are running
2. Verify that you're using the correct IP address and port
3. Ensure your network allows the connection
4. Check the server logs for any error messages

Enjoy seamless file sharing with SwiftShare!
