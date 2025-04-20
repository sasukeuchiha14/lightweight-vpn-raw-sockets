import socket
import threading
import time
import os
import sys
import platform
from encryption import encrypt_data, decrypt_data, load_key

# VPN constants - make port configurable
VPN_PORT = 8989  # Default VPN port
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

def set_vpn_port(port):
    """Set a custom VPN port"""
    global VPN_PORT
    VPN_PORT = port
    if message_callback:
        message_callback(f"VPN port set to {VPN_PORT}", "info")

# Update the queue_message function to prioritize test packets
def queue_message(message):
    """Add a message to the outgoing queue with test packet prioritization"""
    global message_queue
    if message:
        # Check if this is a test packet (for better debugging)
        is_test = "TEST_PACKET" in message or "test packet" in message.lower()
        
        if message_callback:
            if is_test:
                message_callback(f"Queuing TEST PACKET: '{message[:30]}...' ({len(message)} bytes)", "info")
            else:
                message_callback(f"Queuing message: '{message[:20]}...' ({len(message)} bytes)", "info")
        
        # Add test packets to the front of the queue for immediate sending
        if is_test:
            message_queue.insert(0, message)
        else:
            message_queue.append(message)
        return True
    return False

def send_message(sock, message):
    """Encrypt and send a message through the socket"""
    try:
        # Log the send attempt with more details
        if message_callback:
            message_callback(f"Preparing to send message ({len(message)} bytes)", "info")
            
        # Encrypt the message
        encrypted_data = encrypt_data(message.encode('utf-8'))
        
        # Send the data with a size prefix
        message_size = len(encrypted_data)
        size_bytes = message_size.to_bytes(4, byteorder='big')  # 4 bytes for message size
        
        # First send size, then data
        try:
            sock.sendall(size_bytes)
            sock.sendall(encrypted_data)
            if message_callback:
                message_callback(f"Message sent successfully ({message_size+4} bytes)", "info")
                message_callback(message, "packet_sent")
            return True
        except BrokenPipeError:
            if message_callback:
                message_callback("Connection broken - remote peer closed connection", "error")
            return False
        except ConnectionResetError:
            if message_callback:
                message_callback("Connection reset by peer", "error")
            return False
    except Exception as e:
        if message_callback:
            message_callback(f"Error sending message: {str(e)}", "error")
        return False


def handle_incoming_data(sock, client_address):
    """Handle incoming data from a connected client with improved error handling"""
    global running
    
    if message_callback:
        message_callback(f"Started data handler for {client_address}", "info")
    
    try:
        sock.settimeout(5)  # Set timeout to detect closed connections
        
        while running:
            try:
                # First receive message size (4 bytes)
                size_bytes = sock.recv(4)
                if not size_bytes or len(size_bytes) < 4:
                    if message_callback:
                        message_callback("Connection closed by peer or timeout", "info")
                    break
                
                # Convert bytes to integer
                message_size = int.from_bytes(size_bytes, byteorder='big')
                if message_callback:
                    message_callback(f"Receiving message of size {message_size} bytes", "info")
                
                # Now receive the actual message
                encrypted_data = b''
                bytes_received = 0
                
                # Receive in chunks until we get the full message
                while bytes_received < message_size:
                    chunk = sock.recv(min(4096, message_size - bytes_received))
                    if not chunk:
                        raise ConnectionError(f"Connection closed during message receive (got {bytes_received}/{message_size} bytes)")
                    encrypted_data += chunk
                    bytes_received += len(chunk)
                
                # Log successful receive
                if message_callback:
                    message_callback(f"Received complete message ({bytes_received} bytes)", "info")
                
                try:
                    # Decrypt the message
                    decrypted_data = decrypt_data(encrypted_data)
                    message = decrypted_data.decode('utf-8')
                    
                    # Process the received message
                    if message_callback:
                        # For certain system messages, don't count as received data packets
                        if message == "ping" or message == "keep-alive":
                            message_callback(f"Received keepalive ping", "info")
                        else:
                            # This is the critical line to make sure packets appear in the transfer log
                            message_callback(message, "message")
                        
                except Exception as e:
                    if message_callback:
                        message_callback(f"Error decrypting message: {str(e)}", "error")
                        try:
                            # Display key fingerprint for debugging
                            from encryption import load_key
                            key_hex = load_key().hex()
                            key_info = f"Key fingerprint: {key_hex[:8]}...{key_hex[-8:]}"
                            message_callback(f"Using key: {key_info}", "info")
                        except Exception as key_error:
                            message_callback(f"Could not read key: {str(key_error)}", "error")
                        
                        # Log as a failed packet - don't count in statistics
                        message_callback(f"DECRYPTION_FAILED_{time.time()}", "decryption_failed")
                
            except socket.timeout:
                # Just a timeout, continue the loop
                continue
            except ConnectionError as e:
                if message_callback:
                    message_callback(f"Connection error: {str(e)}", "error")
                break
            except Exception as e:
                if message_callback:
                    message_callback(f"Error receiving data: {str(e)}", "error")
                break
                
    except Exception as e:
        if message_callback:
            message_callback(f"Connection handler error: {str(e)}", "error")
    finally:
        # Clean up the connection
        try:
            sock.close()
        except:
            pass
        
        connection_id = f"{client_address}:{VPN_PORT}"
        if connection_id in active_connections:
            del active_connections[connection_id]
        
        if message_callback:
            message_callback(f"Connection handler closed for {client_address}", "info")

def vpn_sender(target_ip, message=None):
    """Establishes a VPN connection to the target IP and sends data"""
    global running
    
    # Initialize connection_id before the try block to prevent UnboundLocalError
    connection_id = f"{target_ip}:{VPN_PORT}"
    sock = None
    
    try:
        # Log detailed connection attempt
        if message_callback:
            remote_address = f"{target_ip}:{VPN_PORT}"
            message_callback(f"Establishing connection to {remote_address} (NAT environment)", "info")
        
        # Create a socket connection with explicit timeout and keep-alive
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)  # Longer timeout for NAT traversal
        
        # Enable TCP keepalive to maintain connection through NAT
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        # Try platform-specific socket options for better NAT handling
        if platform.system() == "Windows":
            # Windows-specific TCP keepalive settings
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 60000, 5000))
        else:
            # Linux/Mac TCP keepalive settings
            if hasattr(socket, 'TCP_KEEPIDLE'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, 'TCP_KEEPCNT'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)
        
        # Connect with detailed error reporting
        try:
            if message_callback:
                message_callback(f"Attempting socket connection to {target_ip}:{VPN_PORT}...", "info")
            sock.connect((target_ip, VPN_PORT))
            if message_callback:
                message_callback(f"Socket connected successfully to {target_ip}:{VPN_PORT}", "info")
        except ConnectionRefusedError:
            if message_callback:
                message_callback(f"Connection refused by {target_ip}:{VPN_PORT} - Check if receiver is running", "error")
            raise
        except TimeoutError:
            if message_callback:
                message_callback(f"Connection timed out to {target_ip}:{VPN_PORT} - Check NAT settings and firewall", "error")
            raise
        
        # Store the connection
        active_connections[connection_id] = sock
        
        # Start a thread to receive messages
        receive_thread = threading.Thread(
            target=handle_incoming_data, 
            args=(sock, target_ip), 
            daemon=True
        )
        receive_thread.start()
        
        # Send an immediate test packet to verify connection
        test_message = "VPN connection established"
        if message_callback:
            message_callback(f"Sending initial test packet...", "info")
        if not send_message(sock, test_message):
            if message_callback:
                message_callback("Failed to send initial test packet", "error")
        
        # If a specific message was provided, send it
        if message:
            if send_message(sock, message):
                if message_callback:
                    message_callback(f"Direct message sent successfully", "info")
            else:
                if message_callback:
                    message_callback(f"Failed to send direct message", "error")
            return
        
        # Keep connection alive and process message queue
        last_activity = time.time()
        ping_interval = 15  # Send ping every 15 seconds if no activity (shorter for NAT)
        retry_interval = 0.5  # Retry failed messages after this delay
        
        while running:
            # Check if there are messages in the queue
            messages_sent = False
            
            # Create a copy of the queue to safely iterate
            current_queue = list(message_queue)
            
            for msg in current_queue:
                if message_callback:
                    message_callback(f"Processing queued message: {msg[:20]}...", "info")
                
                send_success = send_message(sock, msg)
                if send_success:
                    message_queue.remove(msg)
                    messages_sent = True
                    last_activity = time.time()
                else:
                    if message_callback:
                        message_callback(f"Failed to send message, will retry", "error")
                    # Only remove from queue after several retries
                    # This approach keeps the current design, but you might want to add a retry counter
                    break
            
            # Send keep-alive ping if no activity for ping_interval
            current_time = time.time()
            if current_time - last_activity > ping_interval:
                if message_callback:
                    message_callback("Sending keepalive ping", "info")
                if send_message(sock, "ping"):
                    last_activity = current_time
            
            # Sleep to prevent CPU hogging
            time.sleep(retry_interval)
            
    except ConnectionRefusedError:
        if message_callback:
            message_callback(f"Connection refused by {target_ip}:{VPN_PORT}. Check if the receiver is running.", "error")
    except ConnectionResetError:
        if message_callback:
            message_callback("Connection reset by peer. Remote host disconnected.", "error")
    except socket.timeout:
        if message_callback:
            message_callback(f"Connection timed out to {target_ip}:{VPN_PORT}. Check firewall and NAT settings.", "error")
    except Exception as e:
        if message_callback:
            message_callback(f"VPN sender error: {str(e)}", "error")
    finally:
        # Clean up
        if sock:
            try:
                sock.close()
            except:
                pass
        
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
        # Create server socket with reuse address option
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Try to bind with detailed error reporting
        try:
            if message_callback:
                message_callback(f"Binding to all interfaces (0.0.0.0:{VPN_PORT})", "info")
            server_socket.bind(('0.0.0.0', VPN_PORT))
            if message_callback:
                message_callback(f"Successfully bound to 0.0.0.0:{VPN_PORT}", "info")
        except OSError as e:
            if message_callback:
                message_callback(f"Failed to bind to port {VPN_PORT}: {str(e)}", "error")
                message_callback("Port may be in use or blocked. Try a different port.", "error")
            raise
        
        server_socket.listen(MAX_CONNECTIONS)
        server_socket.settimeout(1)  # Set timeout for accept to allow checking running flag
        
        # Print all available network interfaces for debugging
        if message_callback:
            message_callback(f"VPN receiver listening on port {VPN_PORT}", "info")
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                message_callback(f"Local hostname: {hostname}, IP: {local_ip}", "info")
                
                # Try to get all network interfaces
                message_callback("Available network interfaces:", "info")
                for interface, addresses in socket.getaddrinfo(hostname, None):
                    message_callback(f"  {addresses[0]}: {addresses[4][0]}", "info")
            except Exception as e:
                message_callback(f"Error getting network info: {str(e)}", "info")
        
        if message_callback:
            message_callback(f"VPN receiver active - Waiting for connections", "info")
        
        while running:
            try:
                # Accept incoming connection
                client_socket, client_address = server_socket.accept()
                client_ip = client_address[0]
                client_port = client_address[1]
                
                if message_callback:
                    message_callback(f"Connection accepted from {client_ip}:{client_port}", "info")
                
                # Enable TCP keepalive on client socket
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                
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
                if send_message(client_socket, "Connected to VPN receiver"):
                    if message_callback:
                        message_callback(f"Welcome message sent to {client_ip}", "info")
                else:
                    if message_callback:
                        message_callback(f"Failed to send welcome message to {client_ip}", "error")
                
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
            try:
                server_socket.close()
            except:
                pass
        
        if message_callback:
            message_callback("VPN receiver stopped", "info")

def stop_vpn():
    """Stop all VPN connections"""
    global running
    running = False
    
    # Close all active connections
    if message_callback:
        message_callback(f"Stopping VPN - closing {len(active_connections)} active connections", "info")
    
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
        message_callback("VPN stopped successfully", "info")
