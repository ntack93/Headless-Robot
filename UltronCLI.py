#!/home/ec2-user/Headless-Robot/venv/bin/python
import asyncio
import sys
import logging
import argparse
import signal
import importlib.util
import telnetlib3
from colorama import init, Fore, Style
import os
import json
import concurrent.futures


# Initialize colorama for Linux
init(strip=False)

class MockTk:
    """Minimal mock Tkinter for headless operation"""
    def __init__(self):
        self._w = '.'
        self.children = {}
        self._title = ""
        
    def withdraw(self): pass
    def update(self): pass
    # filepath: c:\Users\Noah\OneDrive\Documents\Headless Robot\UltronCLI.py
    def after(self, delay_ms, callback, *args):
        """Schedule a function to be called after a delay."""
        if not callable(callback):
            return None
        
        def wrapper():
            try:
                callback(*args)
            except Exception as e:
                print(f"Error in scheduled callback: {e}")
    
        # Convert Tkinter milliseconds to asyncio seconds
        delay_sec = delay_ms / 1000.0
    
        # Schedule using the global event loop if available
        if hasattr(asyncio, 'get_event_loop'):
            try:
                loop = asyncio.get_event_loop()
                return loop.call_later(delay_sec, wrapper)
            except RuntimeError:
                pass  # No event loop available
            
        return None  # Return None if scheduling failed

    def mainloop(self): pass
    def winfo_exists(self): return True
    def configure(self, **kwargs): pass
    def title(self, text=""): 
        self._title = text
    def destroy(self): pass
    def get_title(self): 
        return self._title
    def nametowidget(self, name): return self

class MockWidget:
    """Base mock widget class"""
    def __init__(self, *args, **kwargs): pass
    def pack(self, *args, **kwargs): pass
    def grid(self, *args, **kwargs): pass
    def configure(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def yview(self, *args): pass
    def see(self, *args): pass
    def set(self, *args): pass  # Add set method for scrollbars

class MockText(MockWidget):
    """Mock Text widget with scrolling support"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""
        self._current_tags = []
        
    def configure(self, *args, **kwargs): pass
    def pack(self, *args, **kwargs): pass
    def insert(self, index, text, *tags): 
        self._text += text
        self._current_tags = list(tags)
    def see(self, *args): pass
    def tag_configure(self, *args, **kwargs): pass
    def get(self, start='1.0', end='end'): return self._text
    def yview(self, *args): pass
    def yview_moveto(self, fraction): pass
    def yview_scroll(self, number, what): pass

class MockVar:
    """Mock variable class for Tkinter variables"""
    def __init__(self, *args, **kwargs):
        self._value = kwargs.get('value', None)
        if not self._value and args:
            self._value = args[0] if args else None
    
    def set(self, value): 
        self._value = value
    
    def get(self): 
        return self._value
    
    def trace_add(self, *args, **kwargs): pass
    def trace_remove(self, *args, **kwargs): pass
    def trace(self, *args, **kwargs): pass

class MockMenu:
    """Mock Menu class for context menus"""
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.items = []

    def add_command(self, **kwargs): pass
    def add_separator(self, **kwargs): pass
    def delete(self, *args): pass
    def entryconfigure(self, *args, **kwargs): pass
    def tk_popup(self, *args, **kwargs): pass
    def post(self, *args, **kwargs): pass
    def unpost(self): pass

class MockScrollbar(MockWidget):
    """Mock Scrollbar with set method"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._first = 0.0
        self._last = 1.0
    
    def set(self, first, last):
        self._first = float(first)
        self._last = float(last)
    
    def get(self):
        return self._first, self._last

class BBSBotCLI:
    def __init__(self, args):
        self.setup_logging()
        # Create comprehensive mock Tkinter environment
        mock_tkinter = type('MockTkinter', (), {
            'Tk': MockTk,
            'Frame': type('Frame', (MockWidget,), {}),
            'Text': MockText,  # Use our enhanced MockText class
            'Label': type('Label', (MockWidget,), {}),
            'Entry': type('Entry', (MockWidget,), {}),
            'Button': type('Button', (MockWidget,), {}),
            'Checkbutton': type('Checkbutton', (MockWidget,), {}),
            'Scrollbar': MockScrollbar,  # Use dedicated MockScrollbar class
            'Menu': MockMenu,  # Add the Menu class
            'StringVar': lambda master=None, value=None, name=None: MockVar(value=value),
            'IntVar': lambda master=None, value=None, name=None: MockVar(value=value),
            'BooleanVar': lambda master=None, value=None, name=None: MockVar(value=value),
            'NORMAL': 'normal',
            'DISABLED': 'disabled',
            'END': 'end',
            'LEFT': 'left',
            'RIGHT': 'right',
            'TOP': 'top',
            'BOTTOM': 'bottom',
            'BOTH': 'both',
            'X': 'x',
            'Y': 'y',
            'HORIZONTAL': 'horizontal',
            'VERTICAL': 'vertical',
            'W': 'w',
            'E': 'e',
            'N': 'n',
            'S': 's',
            'WORD': 'word',  # Add WORD constant
            'CHAR': 'char',  # Add CHAR constant for completeness
            'NONE': 'none',  # Add NONE constant for completeness
        })

        # Create mock ttk module with same widget set
        mock_ttk = type('MockTtk', (), {
            'Frame': type('Frame', (MockWidget,), {}),
            'Label': type('Label', (MockWidget,), {}),
            'Entry': type('Entry', (MockWidget,), {}),
            'Button': type('Button', (MockWidget,), {}),
            'Checkbutton': type('Checkbutton', (MockWidget,), {}),
            'Scrollbar': MockScrollbar,  # Use dedicated MockScrollbar class here too
            'LabelFrame': type('LabelFrame', (MockWidget,), {}),
            'Combobox': type('Combobox', (MockWidget,), {
                'set': lambda *a: None,
                'get': lambda *a: '',
                'current': lambda *a: None
            })
        })

        # Add ttk module to mock tkinter
        mock_tkinter.ttk = mock_ttk

        # Install the mock tkinter
        sys.modules['tkinter'] = mock_tkinter
        
        # Import UltronPreAlpha using platform-independent path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ultron_path = os.path.join(script_dir, "UltronPreAlpha.py")
        spec = importlib.util.spec_from_file_location("UltronPreAlpha", ultron_path)
        ultron_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ultron_module)
        
        # Create instance of the original bot with mock Tk
        self.bot = ultron_module.BBSBotApp(MockTk())
        
        # Store reference to the bot's command processor
        self.command_processor = getattr(self.bot, 'command_processor', None)
        
        # Override connection settings with defaults
        self.host = args.host or "upsidedownmagic.net"  # Set default host
        self.port = args.port or 23  # Set default port
        self.bot.host = self.host
        self.bot.port = self.port
        
        # Set up the event loop
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            print("Event loop initialized successfully")
        except Exception as e:
            print(f"Failed to initialize event loop: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Initialize state
        self.stop_event = asyncio.Event()
        
        # Override the bot's send_full_message method
        self.bot.send_full_message = self.sync_send_full_message
        self.bot.send_private_message = self.sync_send_private_message
        self.bot.send_page_response = self.sync_send_page_response
        self.bot.send_direct_message = self.sync_send_direct_message

        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 999
        self.cleanup_duration = 600  # 10 minutes in seconds
        self.reconnect_delay = 3  # seconds between reconnection attempts
        self.login_complete = False  # Track if login sequence completed
        self.tasks = []  # Track background tasks

        # Add keep-alive attributes
        self.keep_alive_stop_event = asyncio.Event()
        self.keep_alive_task = None

        # Enable auto-login by default
        self.auto_login_enabled = MockVar(value=True)  # Set auto-login to True
        self.logon_automation_enabled = MockVar(value=True)  # Set logon automation to True

        self.join_timer = None  # Add timer reference
        self.in_teleconference = False  # Add teleconference state

        # Add this flag instead
        self.email_checking_started = False

    def setup_logging(self):
        """Configure logging with platform-independent paths"""
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bbs_bot.log')
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        """Connect to the BBS"""
        try:
            self.bot.reader, self.bot.writer = await telnetlib3.open_connection(
                host=self.host,
                port=self.port,
                encoding='cp437',
                cols=136,
                term='ansi'
            )
            
            # Wait briefly to ensure connection is stable
            await asyncio.sleep(1)
            
            if not self.bot.writer.is_closing():
                self.bot.connected = True
                self.logger.info(f"Connected to {self.host}:{self.port}")
                # Start keep-alive when connection is established
                self.start_keep_alive()
                # Add automatic login sequence
                await self.perform_login_sequence()
                return True
            else:
                self.logger.error("Connection closed immediately after establishing")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            return False

    async def keep_alive(self):
        """Send an <ENTER> keystroke every 10 seconds to keep the connection alive."""
        while not self.keep_alive_stop_event.is_set():
            if self.bot.connected and self.bot.writer:
                try:
                    self.bot.writer.write("\r\n")
                    await self.bot.writer.drain()
                except Exception as e:
                    self.logger.error(f"Error in keep-alive: {e}")
            await asyncio.sleep(10)

    def start_keep_alive(self):
        """Start the keep-alive coroutine."""
        self.keep_alive_stop_event.clear()
        self.keep_alive_task = self.loop.create_task(self.keep_alive())

    def stop_keep_alive(self):
        """Stop the keep-alive coroutine."""
        self.keep_alive_stop_event.set()
        if self.keep_alive_task:
            self.keep_alive_task.cancel()

    async def main_loop(self):
        """Main application loop with automatic connection"""
        # Start connection immediately
        if not await self.connect():
            print(f"{Fore.RED}Failed to connect to {self.host}:{self.port}{Style.RESET_ALL}")
            return

        print(f"{Fore.GREEN}Connected to {self.host}:{self.port}{Style.RESET_ALL}")

        # Start background tasks and track them
        self.tasks = [
            asyncio.create_task(self.handle_user_input()),
            asyncio.create_task(self.read_bbs_output())
        ]
        
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"{Fore.RED}Error in main loop: {e}{Style.RESET_ALL}")
            self.logger.exception("Error in main loop")

    async def handle_user_input(self):
        """Handle user input from command line"""
        while not self.stop_event.is_set():
            try:
                command = await self.loop.run_in_executor(None, input, f"{Fore.GREEN}> {Style.RESET_ALL}")
                if not command.strip():
                    # If empty input (just Enter), send Enter keystroke
                    await self.send_message("\r\n")
                else:
                    await self.process_command(command)
            except EOFError:
                break

    async def process_command(self, command):
        """Process user commands"""
        try:
            if command.startswith('!'):
                # Handle built-in CLI commands
                if command.lower() == '!quit':
                    print("Shutting down...")
                    self.stop_event.set()
                    return
                if command.lower() == '!help':
                    print(f"{Fore.CYAN}Available commands: !quit, !help, !weather, !yt, !chat, !news{Style.RESET_ALL}")
                    return
                
                # Create a fake message format that the bot's trigger system expects
                fake_message = f"From CLI: {command}"
                # Use the bot's process_data_chunk method
                self.bot.process_data_chunk(fake_message)
            else:
                # Direct message sending
                await self.send_message(command)
        except Exception as e:
            print(f"{Fore.RED}Error processing command: {e}{Style.RESET_ALL}")
            self.logger.exception("Command processing error")

    async def send_message(self, message):
        """Send a message to the BBS"""
        try:
            if not self.bot.connected:
                print(f"{Fore.RED}Not connected to BBS{Style.RESET_ALL}")
                return
            
            # Add proper line ending
            full_message = f"{message}\r\n"
            self.bot.writer.write(full_message)
            await self.bot.writer.drain()
        except Exception as e:
            print(f"{Fore.RED}Error sending message: {e}{Style.RESET_ALL}")

    async def read_bbs_output(self):
        """Read and display BBS output with improved message handling"""
        # Add a new variable to track if we've already seen the channel banner
        majorlink_banner_seen = False

        while not self.stop_event.is_set():
            try:
                if not self.bot.connected:
                    if await self.attempt_reconnection():
                        # Reset banner detection on reconnection
                        majorlink_banner_seen = False
                        continue
                    else:
                        break

                data = await self.bot.reader.read(4096)
                if not data:
                    print(f"{Fore.RED}Connection dropped. Initiating cleanup reconnection...{Style.RESET_ALL}")
                    await self.handle_cleanup_maintenance()
                    continue

                # Handle both string and bytes data
                data_str = data if isinstance(data, str) else data.decode('utf-8', errors='ignore')

                # Check for cleanup message or MAIN channel message
                if "finish up and log off." in data_str.lower():
                    print(f"{Fore.YELLOW}Cleanup maintenance detected!{Style.RESET_ALL}")
                    await self.send_message("=x")
                    await self.handle_cleanup_maintenance()
                    continue
                elif "You are in the MAIN channel." in data_str:
                    print(f"{Fore.YELLOW}MAIN channel detected - rejoining majorlink{Style.RESET_ALL}")
                    await self.send_message("join majorlink")
                    continue
                # Modified MajorLink channel detection to avoid repeated messages
                elif (not majorlink_banner_seen and 
                      ("You are in the MajorLink channel" in data_str or 
                       "Topic: General Chat" in data_str or
                       "are here with you." in data_str)):
                    print(f"{Fore.GREEN}MajorLink channel detected!{Style.RESET_ALL}")
                    majorlink_banner_seen = True  # Set flag to avoid repeated messages
                    
                    # Start email checking if not already started
                    if not self.email_checking_started:
                        print(f"{Fore.GREEN}Starting email checking routine{Style.RESET_ALL}")
                        self.initialize_email_checking()
                        self.email_checking_started = True

                # Print received data with proper color
                print(f"{Fore.CYAN}{data_str}{Style.RESET_ALL}", end='')
                sys.stdout.flush()
                
                try:
                    # Let the bot process the data - it will use our overridden send methods
                    self.bot.process_data_chunk(data_str)
                except Exception as e:
                    self.logger.error(f"Error processing data: {e}")
                    self.logger.exception("Full traceback:")

            except Exception as e:
                print(f"{Fore.RED}Error reading from BBS: {e}{Style.RESET_ALL}")
                if not await self.attempt_reconnection():
                    break

        self.bot.connected = False

    async def handle_cleanup_maintenance(self):
        """Handle cleanup maintenance by disconnecting, waiting, and reconnecting."""
        print(f"{Fore.YELLOW}Cleanup maintenance detected. Waiting 5 minutes...{Style.RESET_ALL}")
        
        # Disconnect gracefully
        await self.disconnect()
        
        # Wait 5 minutes
        await asyncio.sleep(300)  # 5 minutes
        
        # Start reconnection attempts with proper retry logic
        self.reconnect_attempts = 0
        while self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            print(f"{Fore.YELLOW}Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}...{Style.RESET_ALL}")
            
            if await self.connect():
                return True
                
            await asyncio.sleep(3)  # Wait 3 seconds between attempts
        
        return False

    async def attempt_reconnection(self, is_cleanup=False):
        """Attempt to reconnect to the BBS with retry logic."""
        self.reconnect_attempts = 0
        while self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            print(f"{Fore.YELLOW}Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}...{Style.RESET_ALL}")
            
            try:
                # Attempt to connect
                if await self.connect():
                    print(f"{Fore.GREEN}Successfully reconnected!{Style.RESET_ALL}")
                    # Wait 10 seconds before starting login sequence
                    await asyncio.sleep(10)
                    await self.perform_login_sequence()
                    return True
                
                # If connection failed, wait before retrying
                await asyncio.sleep(self.reconnect_delay)
            except Exception as e:
                print(f"{Fore.RED}Reconnection attempt failed: {e}{Style.RESET_ALL}")
                await asyncio.sleep(self.reconnect_delay)
        
        print(f"{Fore.RED}Failed to reconnect after {self.max_reconnect_attempts} attempts{Style.RESET_ALL}")
        return False

    async def perform_login_sequence(self):
        """Perform the full login sequence."""
        try:
            # Initial wait after connection
            await asyncio.sleep(5)
            
            # Send initial ENTER
            await self.send_message("\r\n")
            await asyncio.sleep(5)
            
            # Load and send username
            username = self.load_username()
            await self.send_message(username)
            await asyncio.sleep(5)
            
            # Load and send password
            password = self.load_password()
            await self.send_message(password)
            await asyncio.sleep(1)
            
            # Send ENTER after password
            await self.send_message("q")
            await asyncio.sleep(1)

            # Send ENTER after password command
            await self.send_message("\r\n")
            await asyncio.sleep(1)

            # Send ENTER after enter command
            await self.send_message("\r\n")
            await asyncio.sleep(1)
            
            # Send teleconference command
            await self.send_message("/go tele")
            await asyncio.sleep(2)  # Wait 2 seconds
            
            # Send join command
            await self.send_message("join majorlink")
            
            # Start the join timer after 60 seconds
            self.loop.call_later(60, lambda: asyncio.create_task(self.start_join_timer()))
            
            self.login_complete = True
            print(f"{Fore.GREEN}Login sequence completed{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}Error during login sequence: {e}{Style.RESET_ALL}")
            self.logger.exception("Login sequence error")
            self.login_complete = False

    async def start_join_timer(self):
        """Start timer to send 'join majorlink' every 60 seconds"""
        if self.bot.connected and self.bot.writer:
            await self.send_message("join majorlink\r\n")
            self.join_timer = self.loop.call_later(60, lambda: asyncio.create_task(self.start_join_timer()))

            





    def stop_join_timer(self):
        """Stop the join timer if it's running"""
        if self.join_timer:
            self.join_timer.cancel()
            self.join_timer = None

    def load_username(self):
        """Load username from file."""
        try:
            if os.path.exists("username.json"):
                with open("username.json", "r") as file:
                    return json.load(file)
        except Exception as e:
            print(f"{Fore.RED}Error loading username: {e}{Style.RESET_ALL}")
        return ""

    def load_password(self):
        """Load password from file."""
        try:
            if os.path.exists("password.json"):
                with open("password.json", "r") as file:
                    return json.load(file)
        except Exception as e:
            print(f"{Fore.RED}Error loading password: {e}{Style.RESET_ALL}")
        return ""

    async def send_full_message(self, message):
        """Send a full message to the BBS with improved handling for special characters"""
        if not message or not self.bot.connected:
            return

        try:
            # Clean message of problematic characters that might trigger BBS commands
            message = message.replace('?', '').replace('=', '')
            
            # Better detection for Trump posts
            is_trump_post = (
                "DJT Posted on:" in message or 
                "Donald J. Trump" in message or 
                "DJT" in message or 
                message.startswith("Latest Post:") or
                "Posted on:" in message
            )
            
            # Use smaller chunk size to prevent truncation
            max_chunk_size = 240  # Further reduced to ensure no truncation
            
            # Split the message with overlap to prevent word loss
            words = message.split()
            chunks = []
            current_chunk = []
            current_length = 0
            
            for word in words:
                # If adding this word would exceed the max length, create a new chunk
                if current_length + len(word) + 1 > max_chunk_size:
                    chunks.append(' '.join(current_chunk))
                    
                    # Add the last two words to the next chunk to create overlap
                    if len(current_chunk) >= 2:
                        current_chunk = current_chunk[-2:]
                        current_length = sum(len(w) for w in current_chunk) + len(current_chunk) - 1
                    else:
                        current_chunk = []
                        current_length = 0
                    
                    # Add the current word
                    current_chunk.append(word)
                    current_length += len(word) + 1
                else:
                    current_chunk.append(word)
                    current_length += len(word) + 1
            
            # Add the last chunk if it's not empty
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            
            # Send each chunk with appropriate delay
            for chunk in chunks:
                if chunk.strip():  # Only send non-empty chunks
                    full_message = f"{chunk}\r\n"
                    self.bot.writer.write(full_message)
                    await self.bot.writer.drain()
                    print(f"{Fore.YELLOW}-> {chunk}{Style.RESET_ALL}")
                    
                    # Use slightly longer delay between chunks
                    await asyncio.sleep(1.0)  # Increased to 1.0 second
        except Exception as e:
            print(f"{Fore.RED}Error sending message: {e}{Style.RESET_ALL}")

    def sync_send_full_message(self, message):
        """Synchronous wrapper for send_full_message that the bot can call"""
        if not message:
            return
            
        async def wrapped_send():
            # Handle both string and list messages
            if isinstance(message, list):
                # If message is a list, send each item separately
                for item in message:
                    await self.send_full_message(item)
            elif hasattr(message, '__await__'):  # If it's already a coroutine
                await message
            else:
                await self.send_full_message(message)

        try:
            # Check if this is likely a Trump post or other long content
            is_long_message = (
                isinstance(message, str) and (
                    "DJT Posted on:" in message or 
                    "Donald J. Trump" in message or 
                    "DJT" in message or 
                    message.startswith("Latest Post:") or
                    "Posted on:" in message or
                    len(message) > 500  # General length check
                )
            )
            
            # Use a longer timeout for Trump posts
            timeout = 15 if is_long_message else 5
            
            # Start the task without waiting for it to complete
            future = asyncio.run_coroutine_threadsafe(wrapped_send(), self.loop)
            
            try:
                # Wait with appropriate timeout
                future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                # For Trump posts, this is expected and not an error
                if is_long_message:
                    self.logger.info("Long message processing continues in background")
                    print(f"{Fore.YELLOW}Long message continues sending in background{Style.RESET_ALL}")
                else:
                    # For other messages, log as an error
                    self.logger.warning("Message send timed out, but may complete in background")
                    print(f"{Fore.YELLOW}Message send timeout - continuing in background{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error in sync_send_full_message: {e}{Style.RESET_ALL}")
            self.logger.exception("Error in sync_send_full_message")

    def sync_send_private_message(self, username, message):
        """Synchronous wrapper for sending private (whispered) messages"""
        if not message or not username:
            return

        async def wrapped_send():
            messages_to_send = message if isinstance(message, list) else [message]

            for msg in messages_to_send:
                chunks = self.bot.chunk_message(str(msg), 250)
                for chunk in chunks:
                    try:
                        full_message = f"Whisper to {username} {chunk}"
                        await self.send_message(full_message + "\r\n")
                        await asyncio.sleep(0.1)  # Reduced to 0.1 seconds
                        self.logger.info(f"Sent chunk to {username}: {chunk}")
                    except Exception as e:
                        self.logger.error(f"Error sending chunk to {username}: {e}")
                        raise

        try:
            self.logger.info(f"Starting message send to {username}")
            future = asyncio.run_coroutine_threadsafe(wrapped_send(), self.loop)

            try:
                future.result(timeout=5.0)  # Reduced timeout to 5 seconds
                self.logger.info(f"Successfully sent message to {username}")
            except concurrent.futures.TimeoutError:
                self.logger.error(f"Timeout sending message to {username}")
                print(f"{Fore.RED}Message send timeout - check connection{Style.RESET_ALL}")
            except Exception as e:
                self.logger.error(f"Error in message send: {e}")
                print(f"{Fore.RED}Failed to send message: {e}{Style.RESET_ALL}")
        except Exception as e:
            self.logger.error(f"Critical error in sync_send_private_message: {e}")
            print(f"{Fore.RED}Critical error sending message: {e}{Style.RESET_ALL}")

    def sync_send_page_response(self, username, module_or_channel, message):
        """Synchronous wrapper for sending page responses"""
        if not message:
            return
            
        async def wrapped_send():
            chunks = self.bot.chunk_message(message, 250)
            for chunk in chunks:
                full_message = f"/P {username} {chunk}"
                await self.send_message(full_message + "\r\n")
                await asyncio.sleep(0.1)

        try:
            future = asyncio.run_coroutine_threadsafe(wrapped_send(), self.loop)
            future.result(timeout=3)
        except Exception as e:
            print(f"{Fore.RED}Error in sync_send_page_response: {e}{Style.RESET_ALL}")
            self.logger.exception("Error in sync_send_page_response")

    def sync_send_direct_message(self, username, message):
        """Synchronous wrapper for sending direct messages"""
        if not message:
            return
            
        async def wrapped_send():
            chunks = self.bot.chunk_message(message, 250)
            for chunk in chunks:
                full_message = f">{username} {chunk}"
                await self.send_message(full_message + "\r\n")
                await asyncio.sleep(0.1)

        try:
            future = asyncio.run_coroutine_threadsafe(wrapped_send(), self.loop)
            future.result(timeout=3)
        except Exception as e:
            print(f"{Fore.RED}Error in sync_send_direct_message: {e}{Style.RESET_ALL}")
            self.logger.exception("Error in sync_send_direct_message")

    async def disconnect(self):
        """Safely disconnect from the BBS."""
        if self.bot.connected:
            # Stop join timer before disconnecting
            self.stop_join_timer()
            # Stop keep-alive before disconnecting
            self.stop_keep_alive()

            # Reset email checking flag on true disconnection
            self.email_checking_started = False

            try:
                # Send a graceful quit message if needed
                try:
                    await self.send_message("quit")
                except:
                    pass

                # Close the writer
                if self.bot.writer:
                    self.bot.writer.close()
                    try:
                        await self.bot.writer.wait_closed()
                    except:
                        pass

                # Clear the references
                self.bot.reader = None
                self.bot.writer = None
                self.bot.connected = False
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")

    async def shutdown(self, sig):
        """Handle graceful shutdown"""
        self.logger.info(f"Received signal {sig.name}, shutting down")
        self.stop_event.set()
        
        # Stop join timer before shutdown
        self.stop_join_timer()
        # Stop keep-alive before canceling tasks
        self.stop_keep_alive()
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                try:
                    task.cancel()
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.error(f"Error canceling task: {e}")
        
        # Ensure disconnect happens
        try:
            await self.disconnect()
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
        
        # Stop the event loop
        self.loop.stop()

    def run(self):
        """Main entry point with improved shutdown handling"""
        import platform
        os_type = platform.system()
        
        # Only set up signal handlers on POSIX systems (non-Windows)
        if os_type != "Windows":
            def handle_sigint():
                self.logger.info("Received SIGINT, initiating shutdown")
                asyncio.create_task(self.shutdown(signal.SIGINT))
                
            # Add all signal handlers for Unix systems
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
                try:
                    self.loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))
                except (NotImplementedError, AttributeError):
                    self.logger.info(f"Signal handler for {sig} not supported on this platform")
        
        # Windows doesn't support signal handlers through asyncio
        # We'll just use the KeyboardInterrupt exception handler instead

        try:
            self.loop.run_until_complete(self.main_loop())
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt received")
            if os_type != "Windows":
                asyncio.run_coroutine_threadsafe(self.shutdown(signal.SIGINT), self.loop)
            else:
                # On Windows, run shutdown directly
                self.loop.run_until_complete(self.shutdown(signal.SIGINT))
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Rest of the cleanup code remains the same
            # Cancel any pending tasks
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                if not task.done():
                    task.cancel()
            
            # Run loop until tasks complete with timeout
            try:
                self.loop.run_until_complete(
                    asyncio.wait_for(
                        asyncio.gather(*pending, return_exceptions=True),
                        timeout=5
                    )
                )
            except (asyncio.CancelledError, asyncio.TimeoutError):
                self.logger.warning("Some tasks were not completed during shutdown")
            except Exception as e:
                self.logger.error(f"Error during shutdown: {e}")
            
            # Clean up
            try:
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            except Exception as e:
                self.logger.error(f"Error shutting down async generators: {e}")
            
            try:
                self.loop.close()
            except Exception as e:
                self.logger.error(f"Error closing event loop: {e}")

    async def handle_direct_message(self, username, message):
        """Handle direct messages by interpreting them as chat queries."""
        try:
            # Get the ChatGPT response
            response = self.get_chatgpt_response(message, direct=True, username=username)
            
            # Send the response back to the user via direct message
            chunks = self.chunk_message(response, 250)
            for chunk in chunks:
                full_message = f">{username} {chunk}"
                await self.send_message(full_message)
                await asyncio.sleep(0.1)  # Small delay between chunks
        except Exception as e:
            self.logger.error(f"Error handling direct message: {e}")


    def initialize_email_checking(self):
        """Initialize the email checking functionality."""
        try:
            # Check if we already have a scheduled task
            if hasattr(self, 'email_check_task') and self.email_check_task:
                print("Email checking already scheduled - not duplicating")
                return
                
            print("Email checking will start in 10 seconds")
            # Schedule the first check
            self.email_check_task = self.loop.call_later(10, self.check_emails)
            self.email_checking_started = True
        except Exception as e:
            print(f"Failed to initialize email checking: {e}")

    def check_emails(self):
        """Check for incoming emails and schedule next check."""
        try:
            print("Checking incoming emails...")
            
            # Clear existing task reference to prevent duplicates
            if hasattr(self, 'email_check_task'):
                self.email_check_task = None
            
            # Enhanced connection check - don't check emails during reconnection attempts
            if not self.bot.connected or hasattr(self, 'reconnect_attempts') and self.reconnect_attempts > 0:
                print("Not connected to BBS or currently reconnecting, will check mail later")
                self.email_check_task = self.loop.call_later(30, self.check_emails)
                return
                    
            credentials = self.bot.load_email_credentials()
            email_address = credentials.get("sender_email")
            password = credentials.get("sender_password")
            
            if not email_address or not password:
                print("Missing email credentials")
                self.email_check_task = self.loop.call_later(30, self.check_emails)
                return
                    
            print(f"Connecting to email {email_address}")
            
            # Manual IMAP implementation
            import imaplib
            import email
            from email.utils import parseaddr
            
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(email_address, password)
            print("Email login successful!")
            
            mail.select('inbox')
            print("Selected inbox")
            
            # One more connection check before proceeding with potentially resource-intensive operations
            if not self.bot.connected:
                print("Connection lost during email check, aborting")
                mail.logout()
                self.email_check_task = self.loop.call_later(30, self.check_emails)
                return
            
            # Search for unread emails with subject 'BBS'
            status, messages = mail.search(None, '(UNSEEN SUBJECT "BBS")')
            print(f"Email search status: {status}")
            
            message_nums = messages[0].split()
            if message_nums:
                print(f"Found {len(message_nums)} new BBS emails")
                
                # Process each email
                for num in message_nums:
                    # Check connection state before processing each email
                    if not self.bot.connected:
                        print("Connection lost while processing emails, marking remaining as unread")
                        mail.logout()
                        self.email_check_task = self.loop.call_later(30, self.check_emails)
                        return
                        
                    status, data = mail.fetch(num, '(RFC822)')
                    if status != 'OK':
                        print(f"Error fetching message {num}: {status}")
                        continue
                        
                    email_msg = email.message_from_bytes(data[0][1])
                    sender = parseaddr(email_msg['From'])[1]
                    
                    # Get body
                    body = ""
                    if email_msg.is_multipart():
                        for part in email_msg.walk():
                            if part.get_content_type() == "text/plain":
                                try:
                                    body = part.get_payload(decode=True).decode('utf-8')
                                except UnicodeDecodeError:
                                    body = part.get_payload(decode=True).decode('latin-1')
                                break
                    else:
                        try:
                            body = email_msg.get_payload(decode=True).decode('utf-8')
                        except UnicodeDecodeError:
                            body = email_msg.get_payload(decode=True).decode('latin-1')
                    
                    # Truncate to 230 characters if needed
                    if len(body) > 230:
                        body = body[:227] + "..."
                        
                    # Clean the body text
                    body = ' '.join(body.split())
                    
                    # Format message for display - CORRECT FORMAT HERE
                    formatted_message = f"Incoming message via eMail: {body}"
                    print(f"Processing email: {formatted_message}")
                    
                    # Check connection again before sending to BBS - ALWAYS send regardless of no_spam mode
                    if self.bot.writer and self.bot.connected:
                        # Create task using the correct send_message method
                        self.loop.create_task(self.send_message(formatted_message))
                        print("Message sent to BBS chat")
                        
                        # Mark as read only if message was sent successfully
                        mail.store(num, '+FLAGS', '\\Seen')
                        print(f"Email marked as read")
                    else:
                        print("Not sending to BBS due to disconnection - will retry later")
                        mail.logout()
                        self.email_check_task = self.loop.call_later(30, self.check_emails)
                        return
                
            else:
                print("No new BBS emails")
            
            mail.logout()
            print("Email check complete")
            
        except Exception as e:
            print(f"Error checking emails: {str(e)}")
            
        finally:
            # Schedule next check only if not already in reconnection sequence
            if hasattr(self, 'reconnect_attempts') and self.reconnect_attempts == 0:
                print("Scheduling next email check in 30 seconds")
                self.email_check_task = self.loop.call_later(30, self.check_emails)
            else:
                print("In reconnection sequence - email checking will resume after reconnection")

    def process_data_chunk(self, data):
        """Process incoming data chunks."""

        # Check for direct messages
        direct_message_match = re.match(r'From (.+?) \(to you\): (.+)', clean_line)
        if direct_message_match:
            username = direct_message_match.group(1)
            message = direct_message_match.group(2)
            asyncio.run_coroutine_threadsafe(
                self.handle_direct_message(username, message), 
                self.loop
            )
            return


def main():
    parser = argparse.ArgumentParser(description='BBS Chatbot CLI')
    parser.add_argument('--host', help='BBS host address', default="upsidedownmagic.net")
    parser.add_argument('--port', type=int, help='BBS port number', default=23)
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI dependencies')
    
    args = parser.parse_args()
    
    print("BBS Chatbot CLI")
    print("---------------")
    print(f"Connecting to {args.host}:{args.port}...")
    
    try:
        bot = BBSBotCLI(args)
        bot.run()
    except KeyboardInterrupt:
        print("\nShutdown requested via Ctrl+C")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()  # Print the full traceback for better debugging
    finally:
        print("Shutdown complete")

if __name__ == "__main__":
    main()
