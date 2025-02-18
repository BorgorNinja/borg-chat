import socket, threading, datetime

# Dictionary mapping channel names to lists of client sockets.
channels = {}  
# Dictionary mapping client sockets to their metadata (nickname, channel).
clients = {}   
# Persistent chat history for each channel.
chat_history = {}  

def broadcast(message, channel, sender_socket=None):
    """Broadcast a message to all clients in a channel except the sender (if provided)."""
    if channel in channels:
        for client in channels[channel]:
            # Optionally, skip the sender if desired.
            if client != sender_socket:
                try:
                    client.send(message.encode())
                except Exception as e:
                    print("Broadcast error:", e)

def handle_client(client_socket, address):
    # Set a default nickname.
    nickname = f"User{address[1]}"
    clients[client_socket] = {"nickname": nickname, "channel": None}
    client_socket.send("Welcome! Use /nick <name> to set your nickname.\n".encode())
    
    while True:
        try:
            message = client_socket.recv(4096).decode()
            if not message:
                break
            
            # Process commands starting with '/'
            if message.startswith("/"):
                parts = message.strip().split(" ", 1)
                command = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                
                if command == "/nick":
                    old_nick = clients[client_socket]["nickname"]
                    new_nick = args.strip()
                    clients[client_socket]["nickname"] = new_nick
                    client_socket.send(f"Nickname changed from {old_nick} to {new_nick}\n".encode())
                
                elif command == "/create":
                    channel_name = args.strip()
                    if channel_name in channels:
                        client_socket.send("Channel already exists.\n".encode())
                    else:
                        channels[channel_name] = []
                        chat_history[channel_name] = []  # Initialize history for the channel.
                        client_socket.send(f"Channel '{channel_name}' created.\n".encode())
                
                elif command == "/join":
                    channel_name = args.strip()
                    if channel_name not in channels:
                        client_socket.send("Channel does not exist. Create it with /create <channel>\n".encode())
                    else:
                        # If already in a channel, remove the client.
                        old_channel = clients[client_socket]["channel"]
                        if old_channel:
                            if client_socket in channels[old_channel]:
                                channels[old_channel].remove(client_socket)
                                broadcast(f"{clients[client_socket]['nickname']} has left the channel.", old_channel, client_socket)
                        channels[channel_name].append(client_socket)
                        clients[client_socket]["channel"] = channel_name
                        
                        # Send existing chat history for the channel.
                        if channel_name in chat_history:
                            for line in chat_history[channel_name]:
                                client_socket.send((line + "\n").encode())
                        
                        join_msg = f"Joined channel '{channel_name}'"
                        client_socket.send(join_msg.encode())
                        broadcast(f"{clients[client_socket]['nickname']} has joined the channel.", channel_name, client_socket)
                
                elif command == "/list":
                    ch_list = ", ".join(channels.keys()) if channels else "No channels available."
                    client_socket.send(f"Available channels: {ch_list}\n".encode())
                
                elif command == "/dm":
                    try:
                        target_nick, dm_message = args.split(" ", 1)
                        target_socket = None
                        for sock, info in clients.items():
                            if info["nickname"] == target_nick:
                                target_socket = sock
                                break
                        if target_socket:
                            target_socket.send(f"DM from {clients[client_socket]['nickname']}: {dm_message}\n".encode())
                        else:
                            client_socket.send("User not found.\n".encode())
                    except Exception:
                        client_socket.send("Usage: /dm <nickname> <message>\n".encode())
                
                elif command == "/status":
                    # This can be extended to update and broadcast user status.
                    client_socket.send("Status updated.\n".encode())
                
                elif command == "/img":
                    # Handle image command.
                    channel = clients[client_socket]["channel"]
                    if channel:
                        # Broadcast the image command to all clients in the channel.
                        broadcast(message, channel, sender_socket=client_socket)
                        # Save the image command in the channel's history.
                        if channel in chat_history:
                            chat_history[channel].append(message)
                        else:
                            chat_history[channel] = [message]
                    else:
                        client_socket.send("Join a channel first using /join <channel>\n".encode())
                
                elif command == "/quit":
                    client_socket.send("Goodbye!\n".encode())
                    break
                
                else:
                    client_socket.send("Unknown command.\n".encode())
            else:
                # Normal text message: broadcast it and store in chat history.
                channel = clients[client_socket]["channel"]
                if channel:
                    current_time = datetime.datetime.now().strftime('%H:%M')
                    formatted_message = f"[{current_time} : {clients[client_socket]['nickname']}] {message}"
                    if channel in chat_history:
                        chat_history[channel].append(formatted_message)
                    else:
                        chat_history[channel] = [formatted_message]
                    broadcast(formatted_message, channel, sender_socket=client_socket)
                else:
                    client_socket.send("Join a channel first using /join <channel>\n".encode())
                    
        except Exception as e:
            print("Client handling error:", e)
            break
    
    # Cleanup on disconnect.
    channel = clients[client_socket]["channel"]
    if channel and client_socket in channels.get(channel, []):
        channels[channel].remove(client_socket)
        broadcast(f"{clients[client_socket]['nickname']} has disconnected.", channel, client_socket)
    client_socket.close()
    del clients[client_socket]

def start_server(ip="0.0.0.0", port=12345):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((ip, port))
    server.listen(5)
    print(f"Chat server started on {ip}:{port}")
    
    while True:
        client_socket, address = server.accept()
        print("New connection from", address)
        threading.Thread(target=handle_client, args=(client_socket, address)).start()

if __name__ == "__main__":
    start_server()
