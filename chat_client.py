import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import socket, threading, queue, datetime, base64, io
from PIL import Image, ImageTk

class ChatClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Decentralized Chat Client")
        self.geometry("800x600")
        self.msg_queue = queue.Queue()
        self.socket = None
        self.running = False
        self.username = "You"  # Default username
        self.current_channel = None  # Currently active channel
        self.chat_logs = {}   # Separate chat logs per channel.
        self.images = []      # To store image references for the chat display

        self.create_widgets()
        self.create_menu()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.connect_to_server()

    def create_widgets(self):
        # Top frame shows connected node's IP and Port.
        top_frame = ttk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        self.node_info_label = ttk.Label(top_frame, text="Not connected")
        self.node_info_label.pack(side=tk.LEFT)

        # Main frame: Channel list on left, chat area on right.
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left frame: Channel List.
        left_frame = ttk.Frame(main_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        left_label = ttk.Label(left_frame, text="Channel List")
        left_label.pack(pady=5)
        self.channel_listbox = tk.Listbox(left_frame)
        self.channel_listbox.pack(fill=tk.BOTH, expand=True, padx=5)
        self.channel_listbox.bind("<Double-Button-1>", self.join_channel_from_list)

        # Right frame: Chat messages and message input.
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.chat_text = scrolledtext.ScrolledText(right_frame, state="disabled")
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        # Bottom frame: [Upload Image] [Message Entry] [Emoji] [Send]
        bottom_frame = ttk.Frame(right_frame)
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)
        self.upload_button = ttk.Button(bottom_frame, text="[Upload Image]", command=self.upload_image)
        self.upload_button.grid(row=0, column=0, padx=5)
        self.message_entry = ttk.Entry(bottom_frame)
        self.message_entry.grid(row=0, column=1, padx=5, sticky="ew")
        self.message_entry.bind("<Return>", lambda event: self.send_message())
        self.emoji_button = ttk.Button(bottom_frame, text="[Emoji]", command=self.show_emoji_picker)
        self.emoji_button.grid(row=0, column=2, padx=5)
        self.send_button = ttk.Button(bottom_frame, text="[Send]", command=self.send_message)
        self.send_button.grid(row=0, column=3, padx=5)
        bottom_frame.columnconfigure(1, weight=1)

    def create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Commands Help", command=self.show_help)
        menubar.add_cascade(label="Help", menu=help_menu)

    def show_help(self):
        help_text = (
            "Available Commands:\n"
            "/nick <name>       : Set your nickname.\n"
            "/create <channel>  : Create a new channel.\n"
            "/join <channel>    : Join an existing channel.\n"
            "/list              : List all available channels.\n"
            "/dm <nick> <msg>   : Send a direct message to a user.\n"
            "/status <state>    : Set your status (online, away, busy).\n"
            "/history           : View message history.\n"
            "/file              : Send a file (feature not implemented).\n"
            "/img <username> <time> <base64> : Image message format (handled automatically).\n"
            "/quit              : Disconnect from the server.\n"
            "\nUsage:\n"
            "Type your message in the box and press Enter or click [Send].\n"
            "Double-click a channel in the Channel List to join it.\n"
            "Click [Upload Image] to select and send an image.\n"
            "Click [Emoji] to add an emoji to your message.\n"
        )
        messagebox.showinfo("Help", help_text)

    def connect_to_server(self):
        dialog = tk.Toplevel(self)
        dialog.title("Connect to Server")
        dialog.grab_set()
        ttk.Label(dialog, text="Server IP:").grid(row=0, column=0, padx=5, pady=5)
        ip_entry = ttk.Entry(dialog)
        ip_entry.grid(row=0, column=1, padx=5, pady=5)
        ip_entry.insert(0, "127.0.0.1")
        ttk.Label(dialog, text="Port:").grid(row=1, column=0, padx=5, pady=5)
        port_entry = ttk.Entry(dialog)
        port_entry.grid(row=1, column=1, padx=5, pady=5)
        port_entry.insert(0, "12345")

        def on_connect():
            ip = ip_entry.get().strip()
            port = int(port_entry.get().strip())
            self.node_info_label.config(text=f"Connected to: {ip}:{port}")
            dialog.destroy()
            self.start_connection(ip, port)

        connect_button = ttk.Button(dialog, text="Connect", command=on_connect)
        connect_button.grid(row=2, column=0, columnspan=2, pady=10)
        dialog.wait_window()

    def start_connection(self, ip, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((ip, port))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")
            self.destroy()
            return
        self.running = True
        threading.Thread(target=self.receive_messages, daemon=True).start()
        self.send_command("/list")

    def receive_messages(self):
        while self.running:
            try:
                message = self.socket.recv(4096).decode()
                if message:
                    self.msg_queue.put(message)
                else:
                    break
            except Exception:
                break
        if self.socket:
            self.socket.close()

    def process_queue(self):
        while not self.msg_queue.empty():
            message = self.msg_queue.get()
            # Update channel list if applicable.
            if message.startswith("Available channels:"):
                channels_str = message.replace("Available channels:", "").strip()
                channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]
                self.update_channel_list(channels)
            # Handle join confirmations.
            elif message.startswith("Joined channel"):
                try:
                    channel = message.split("'")[1]
                    self.switch_channel(channel)
                    self.append_to_channel_log(channel, message)
                except IndexError:
                    self.display_message(message)
            # Handle image messages.
            elif message.startswith("/img "):
                parts = message.split(" ", 3)
                if len(parts) < 4:
                    self.display_message(message)
                else:
                    sender = parts[1]
                    time_str = parts[2]
                    b64_data = parts[3]
                    formatted_msg = f"[{time_str} : {sender}] sent an image:"
                    self.append_to_channel_log(self.current_channel, formatted_msg)
                    try:
                        image_bytes = base64.b64decode(b64_data)
                        self.display_image(image_bytes)
                    except Exception as e:
                        self.display_message("Failed to decode image.")
            else:
                # Regular text message.
                if self.current_channel:
                    self.append_to_channel_log(self.current_channel, message)
                else:
                    self.display_message(message)
        self.after(100, self.process_queue)

    def display_message(self, message):
        self.chat_text.configure(state="normal")
        self.chat_text.insert(tk.END, message + "\n")
        self.chat_text.configure(state="disabled")
        self.chat_text.see(tk.END)

    def display_image(self, image_bytes):
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception:
            self.display_message("Error opening image.")
            return

        max_width = 200
        if image.width > max_width:
            ratio = max_width / image.width
            new_size = (max_width, int(image.height * ratio))
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.ANTIALIAS
            image = image.resize(new_size, resample_filter)
        photo = ImageTk.PhotoImage(image)
        self.chat_text.configure(state="normal")
        self.chat_text.image_create(tk.END, image=photo)
        self.chat_text.insert(tk.END, "\n")
        self.chat_text.configure(state="disabled")
        self.chat_text.see(tk.END)
        self.images.append(photo)

    def append_to_channel_log(self, channel, message):
        if channel not in self.chat_logs:
            self.chat_logs[channel] = []
        self.chat_logs[channel].append(message)
        if self.current_channel == channel:
            self.display_message(message)

    def update_channel_list(self, channels):
        self.channel_listbox.delete(0, tk.END)
        for channel in channels:
            self.channel_listbox.insert(tk.END, channel)

    def switch_channel(self, channel):
        self.current_channel = channel
        if channel not in self.chat_logs:
            self.chat_logs[channel] = []
        self.chat_text.configure(state="normal")
        self.chat_text.delete(1.0, tk.END)
        for msg in self.chat_logs[channel]:
            self.chat_text.insert(tk.END, msg + "\n")
        self.chat_text.configure(state="disabled")

    def join_channel_from_list(self, event):
        selection = self.channel_listbox.curselection()
        if selection:
            channel = self.channel_listbox.get(selection[0])
            self.send_command(f"/join {channel}")
            self.switch_channel(channel)

    def send_message(self):
        msg = self.message_entry.get().strip()
        if msg and self.socket:
            # Update username if using /nick.
            if msg.startswith("/nick "):
                parts = msg.split(" ", 1)
                if len(parts) > 1:
                    self.username = parts[1].strip()
            # Echo non-command messages locally with timestamp.
            if not msg.startswith("/"):
                current_time = datetime.datetime.now().strftime('%H:%M')
                formatted_msg = f"[{current_time} : {self.username}] {msg}"
                if self.current_channel:
                    self.append_to_channel_log(self.current_channel, formatted_msg)
                else:
                    self.display_message(formatted_msg)
            self.socket.send(msg.encode())
            self.message_entry.delete(0, tk.END)

    def upload_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif")])
        if file_path and self.socket:
            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                b64_data = base64.b64encode(file_bytes).decode('utf-8')
                current_time = datetime.datetime.now().strftime('%H:%M')
                formatted_msg = f"[{current_time} : {self.username}] sent an image:"
                if self.current_channel:
                    self.append_to_channel_log(self.current_channel, formatted_msg)
                else:
                    self.display_message(formatted_msg)
                self.display_image(file_bytes)
                command = f"/img {self.username} {current_time} {b64_data}"
                self.socket.send(command.encode())
            except Exception as e:
                messagebox.showerror("Image Error", f"Failed to send image: {e}")

    def show_emoji_picker(self):
        picker = tk.Toplevel(self)
        picker.title("Emoji Picker")
        emojis = ["😀", "😂", "😍", "😎", "👍", "🔥", "🎉", "🤖", "🙌", "💯"]
        def insert_emoji(emoji):
            self.message_entry.insert(tk.END, emoji)
            picker.destroy()
        for i, emoji in enumerate(emojis):
            btn = ttk.Button(picker, text=emoji, command=lambda e=emoji: insert_emoji(e))
            btn.grid(row=i // 5, column=i % 5, padx=5, pady=5)
    
    def send_command(self, command):
        if self.socket:
            self.socket.send(command.encode())

    def on_closing(self):
        if self.socket:
            try:
                self.socket.send("/quit".encode())
            except:
                pass
        self.running = False
        self.destroy()

if __name__ == "__main__":
    app = ChatClient()
    app.after(100, app.process_queue)
    app.mainloop()
