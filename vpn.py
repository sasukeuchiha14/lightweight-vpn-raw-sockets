import socket
import threading
import time
import os
import sys
import platform
from encryption import encrypt_data, decrypt_data

# VPN constants
VPN_PORT = 8989  # Port for VPN connections
BUFFER_SIZE = 4096
MAX_CONNECTIONS = 5
running = True  # Global flag to control VPN threads
active_connections = {}  # Store active connections
message_queue = []  # Queue for outgoing messages
message_callback = None  # Callback for received messages

def set_message_callback(callback):
    """Set the callback function for handling received messages"""
    global message_callback
    message_callback = callback

def queue_message(message):
    """Add a message to the outgoing queue"""
    global message_queue
    if message:
        if message_callback:
            message_callback(f"Queuing message: '{message[:20]}...' ({len(message)} bytes)", "info")
        message_queue.append(message)
        return True
    return False

def send_message(sock, message):
    """Encrypt and send a message through the socket"""
    try:
        # Log the send attempt
        if message_callback:
            message_callback(f"Sending message ({len(message)} bytes)", "info")
            
        # Encrypt the message
        encrypted_data = encrypt_data(message.encode('utf-8'))
        
        # Send the data with a size prefix
        message_size = len(encrypted_data)
        size_bytes = message_size.to_bytes(4, byteorder='big')  # 4 bytes for message size
        
        # First send size, then data
        sock.sendall(size_bytes)
        sock.sendall(encrypted_data)
        
        # Log successful send
        if message_callback:
            message_callback(message, "packet_sent")
            
        return True
    except Exception as e:
        if message_callback:
            message_callback(f"Error sending message: {str(e)}", "error")
        return False

def handle_incoming_data(sock, client_address):
    """Handle incoming data from a connected client"""
    global running
    
    try:
        sock.settimeout(5)  # Set timeout to detect closed connections
        
        while running:
            try:
                # First receive message size (4 bytes)
                size_bytes = sock.recv(4)
                if not size_bytes or len(size_bytes) < 4:
                    if message_callback:
                        message_callback("Connection closed by peer", "info")
                    break
                
                # Convert bytes to integer
                message_size = int.from_bytes(size_bytes, byteorder='big')
                
                # Now receive the actual message
                encrypted_data = b''
                bytes_received = 0
                
                # Receive in chunks until we get the full message
                while bytes_received < message_size:
                    chunk = sock.recv(min(4096, message_size - bytes_received))
                    if not chunk:
                        raise ConnectionError("Connection closed during message receive")
                    encrypted_data += chunk
                    bytes_received += len(chunk)
                
                # Decrypt the message
                decrypted_data = decrypt_data(encrypted_data)
                message = decrypted_data.decode('utf-8')
                
                # Process the received message
                if message_callback:
                    message_callback(message, "message")
                
            except socket.timeout:
                # Just a timeout, continue the loop
                continue
            except Exception as e:
                if message_callback:
                    message_callback(f"Error receiving data: {str(e)}", "error")
                break
                
    except Exception as e:
        if message_callback:
            message_callback(f"Connection handler error: {str(e)}", "error")
    finally:
        # Clean up the connection
        sock.close()
        connection_id = f"{client_address}:{VPN_PORT}"
        if connection_id in active_connections:
            del active_connections[connection_id]

def vpn_sender(target_ip, message=None):
    """Establishes a VPN connection to the target IP and sends data"""
    global running
    
    # Initialize connection_id before the try block to prevent UnboundLocalError
    connection_id = f"{target_ip}:{VPN_PORT}"
    sock = None
    
    try:
        # Debug log
        if message_callback:
            message_callback(f"Connecting to {target_ip}:{VPN_PORT}", "info")
        
        # Create a socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # Set connection timeout
        sock.connect((target_ip, VPN_PORT))
        
        # Debug log
        if message_callback:
            message_callback(f"Connected to {target_ip}:{VPN_PORT}", "info")
        
        # Store the connection
        active_connections[connection_id] = sock
        
        # Start a thread to receive messages
        receive_thread = threading.Thread(
            target=handle_incoming_data, 
            args=(sock, target_ip), 
            daemon=True
        )
        receive_thread.start()
        
        # If a specific message was provided, send it immediately
        if message:
            if send_message(sock, message):
                if message_callback:
                    message_callback(f"Direct message sent to {target_ip}", "info")
            else:
                if message_callback:
                    message_callback(f"Failed to send direct message to {target_ip}", "error")
            return
        
        # Send an initial test message
        send_message(sock, "VPN connection established")
        
        # Keep connection alive and process message queue
        last_activity = time.time()
        ping_interval = 30  # Send ping every 30 seconds if no activity
        
        while running:
            # Check if there are messages in the queue
            messages_sent = False
            for msg in list(message_queue):  # Create a copy to safely remove items
                if send_message(sock, msg):
                    message_queue.remove(msg)
                    messages_sent = True
                    last_activity = time.time()
                else:
                    # If send fails, leave in queue for retry
                    if message_callback:
                        message_callback(f"Message send failed, will retry", "error")
                    break
            
            # Send keep-alive ping if no activity for ping_interval
            current_time = time.time()
            if current_time - last_activity > ping_interval:
                send_message(sock, "ping")
                last_activity = current_time
            
            # Sleep to prevent CPU hogging
            time.sleep(0.1)
            
    except ConnectionRefusedError:
        if message_callback:
            message_callback(f"Connection refused by {target_ip}. Is the receiver running?", "error")
    except ConnectionResetError:
        if message_callback:
            message_callback("Connection reset by peer. Remote host disconnected.", "error")
    except socket.timeout:
        if message_callback:
            message_callback(f"Connection timed out to {target_ip}", "error")
    except Exception as e:
        if message_callback:
            message_callback(f"VPN sender error: {str(e)}", "error")
    finally:
        # Clean up
        if sock:
            sock.close()
        if connection_id in active_connections:
            del active_connections[connection_id]
        if message_callback:
            message_callback("VPN sender disconnected", "info")

def vpn_receiver():
    """Listens for incoming VPN connections"""
    global running
    
    server_socket = None
    client_threads = []
    
    try:
        # Create server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', VPN_PORT))
        server_socket.listen(5)
        server_socket.settimeout(1)  # Set timeout for accept to allow checking running flag
        
        if message_callback:
            message_callback(f"VPN receiver listening on port {VPN_PORT}", "info")
        
        while running:
            try:
                # Accept incoming connection
                client_socket, client_address = server_socket.accept()
                client_ip = client_address[0]
                
                if message_callback:
                    message_callback(f"Connection accepted from {client_ip}", "info")
                
                # Store the connection
                connection_id = f"{client_ip}:{VPN_PORT}"
                active_connections[connection_id] = client_socket
                
                # Start a thread to handle the client
                client_thread = threading.Thread(
                    target=handle_incoming_data, 
                    args=(client_socket, client_ip),
                    daemon=True
                )
                client_thread.start()
                client_threads.append(client_thread)
                
                # Send welcome message
                send_message(client_socket, "Connected to VPN receiver")
                
            except socket.timeout:
                # This is just the accept timeout, continue the loop
                continue
            except Exception as e:
                if message_callback:
                    message_callback(f"Error accepting connection: {str(e)}", "error")
    
    except Exception as e:
        if message_callback:
            message_callback(f"VPN receiver error: {str(e)}", "error")
    finally:
        # Clean up server
        if server_socket:
            server_socket.close()
        if message_callback:
            message_callback("VPN receiver stopped", "info")

def stop_vpn():
    """Stop all VPN connections"""
    global running
    running = False
    
    # Close all active connections
    for conn_id, sock in list(active_connections.items()):
        try:
            sock.close()
        except:
            pass
    
    active_connections.clear()
    
    # Sleep briefly to let threads clean up
    time.sleep(0.5)
    
    # Reset the running flag for next time
    running = True
    
    if message_callback:
        message_callback("VPN stopped", "info")
