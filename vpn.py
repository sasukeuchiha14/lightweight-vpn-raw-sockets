import socket
import threading
import time
import os
import sys
import platform
from encryption import encrypt_message, decrypt_message

# VPN settings
VPN_PORT = 8888
BUFFER_SIZE = 4096
MAX_CONNECTIONS = 5
running = True
active_connections = {}
message_queue = []
message_callback = None

def set_message_callback(callback):
    """Set a callback function to receive messages from the VPN"""
    global message_callback
    message_callback = callback

def vpn_sender(target_ip, message=None):
    """
    Establishes a VPN connection to the target IP and sends data
    """
    global running
    
    try:
        # Create a socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((target_ip, VPN_PORT))
        
        # Store the connection
        connection_id = f"{target_ip}:{VPN_PORT}"
        active_connections[connection_id] = sock
        
        # Start a thread to receive messages
        receive_thread = threading.Thread(target=handle_incoming_data, args=(sock, target_ip), daemon=True)
        receive_thread.start()
        
        # If a specific message was provided, send it
        if message:
            send_message(sock, message)
            return
        
        # Keep connection alive and process message queue
        while running:
            # Send any queued messages
            for msg in message_queue[:]:
                send_message(sock, msg)
                message_queue.remove(msg)
            time.sleep(0.1)
            
    except Exception as e:
        if message_callback:
            message_callback(f"Connection error: {str(e)}", "error")
        running = False
    finally:
        if connection_id in active_connections:
            del active_connections[connection_id]
        sock.close()

def vpn_receiver():
    """
    Listens for incoming VPN connections
    """
    global running
    
    try:
        # Create a server socket
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(('0.0.0.0', VPN_PORT))
        server_sock.listen(MAX_CONNECTIONS)
        server_sock.settimeout(1.0)  # Use timeout to allow checking running flag
        
        if message_callback:
            message_callback(f"VPN receiver listening on port {VPN_PORT}", "info")
        
        # Accept connections and handle them
        while running:
            try:
                client_sock, client_addr = server_sock.accept()
                connection_id = f"{client_addr[0]}:{client_addr[1]}"
                active_connections[connection_id] = client_sock
                
                if message_callback:
                    message_callback(f"Connection from {client_addr[0]}", "info")
                
                # Start a thread to handle this client
                client_thread = threading.Thread(target=handle_incoming_data, 
                                               args=(client_sock, client_addr[0]), 
                                               daemon=True)
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if message_callback:
                    message_callback(f"Error accepting connection: {str(e)}", "error")
    
    except Exception as e:
        if message_callback:
            message_callback(f"VPN receiver error: {str(e)}", "error")
    finally:
        server_sock.close()
        running = False

def handle_incoming_data(sock, sender_ip):
    """
    Handles incoming data from a connection
    """
    global running
    sock.settimeout(1.0)  # Timeout for checking running flag
    
    try:
        while running:
            try:
                data = sock.recv(BUFFER_SIZE)
                if not data:
                    break  # Connection closed
                
                # Decrypt and process the data
                try:
                    decrypted_message = decrypt_message(data)
                    if message_callback:
                        message_callback(f"{sender_ip}: {decrypted_message}", "message")
                except Exception as e:
                    if message_callback:
                        message_callback(f"Error decrypting message: {str(e)}", "error")
            
            except socket.timeout:
                continue  # Just a timeout, keep looping
            except Exception as e:
                if message_callback:
                    message_callback(f"Error receiving data: {str(e)}", "error")
                break
    
    finally:
        sock.close()
        connection_id = f"{sender_ip}:{VPN_PORT}"
        if connection_id in active_connections:
            del active_connections[connection_id]

def send_message(sock, message):
    """
    Encrypts and sends a message through the VPN
    """
    try:
        encrypted_data = encrypt_message(message)
        sock.sendall(encrypted_data)
        return True
    except Exception as e:
        if message_callback:
            message_callback(f"Error sending message: {str(e)}", "error")
        return False

def queue_message(message):
    """
    Adds a message to the queue to be sent
    """
    message_queue.append(message)

def stop_vpn():
    """
    Stops all VPN connections
    """
    global running
    running = False
    
    # Close all active connections
    for conn_id, sock in active_connections.items():
        try:
            sock.close()
        except:
            pass
    
    active_connections.clear()
