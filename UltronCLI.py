import asyncio
import sys
import logging
import argparse
import signal
import importlib.util
import telnetlib3
from colorama import init, Fore, Style
import os

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
    def after(self, *args): pass
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
        
        # Override connection settings
        self.host = args.host or input("Enter BBS hostname: ").strip()
        self.port = args.port or int(input("Enter port number [23]: ").strip() or "23")
        self.bot.host = self.host
        self.bot.port = self.port
        
        # Set up the event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Initialize state
        self.stop_event = asyncio.Event()
        
        # Override the bot's send_full_message method
        self.bot.send_full_message = self.sync_send_full_message

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
                return True
            else:
                self.logger.error("Connection closed immediately after establishing")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            return False

    async def main_loop(self):
        """Main application loop"""
        if not await self.connect():
            print(f"{Fore.RED}Failed to connect to {self.host}:{self.port}{Style.RESET_ALL}")
            return

        print(f"{Fore.GREEN}Connected to {self.host}:{self.port}{Style.RESET_ALL}")

        # Start background tasks
        input_task = asyncio.create_task(self.handle_user_input())
        read_task = asyncio.create_task(self.read_bbs_output())
        
        try:
            await asyncio.gather(input_task, read_task)
        except asyncio.CancelledError:
            pass

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
        """Read and display BBS output"""
        try:
            while not self.stop_event.is_set() and self.bot.connected:
                data = await self.bot.reader.read(4096)
                if not data:
                    print(f"{Fore.RED}Connection closed by server{Style.RESET_ALL}")
                    break
                
                # Display the output
                print(f"{Fore.WHITE}{data}{Style.RESET_ALL}", end='')
                sys.stdout.flush()
                
                # Process data through the bot's trigger system
                try:
                    # Use the bot's process_data_chunk method instead of parse_incoming_triggers
                    self.bot.process_data_chunk(data)
                except Exception as e:
                    self.logger.error(f"Error processing data: {e}")

        except Exception as e:
            print(f"{Fore.RED}Error reading from BBS: {e}{Style.RESET_ALL}")
        finally:
            self.stop_event.set()
            self.bot.connected = False

    def sync_send_full_message(self, message):
        """Synchronous wrapper for send_full_message that the bot can call"""
        if not message:
            return
        future = asyncio.run_coroutine_threadsafe(self.send_full_message(message), self.loop)
        try:
            # Reduce timeout from 10 to 3 seconds
            future.result(timeout=3)
        except Exception as e:
            print(f"{Fore.RED}Error in sync_send_full_message: {e}{Style.RESET_ALL}")

    async def send_full_message(self, message):
        """Send a full message to the BBS"""
        if not message or not self.bot.connected:
            return

        try:
            # Split message into chunks of maximum 250 characters
            chunks = []
            current_chunk = []
            current_length = 0
            
            # Split by words first
            words = message.split()
            for word in words:
                # If this word would make the chunk too long, send current chunk
                if current_length + len(word) + 1 > 250:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [word]
                    current_length = len(word) + 1
                else:
                    current_chunk.append(word)
                    current_length += len(word) + 1
            
            # Add the last chunk if there is one
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            
            # Send each chunk with minimal delay
            for chunk in chunks:
                if chunk.strip():  # Only send non-empty chunks
                    full_message = f"{chunk}\r\n"
                    self.bot.writer.write(full_message)
                    await self.bot.writer.drain()
                    print(f"{Fore.YELLOW}-> {chunk}{Style.RESET_ALL}")  # Show outgoing message
                    await asyncio.sleep(0.1)  # Reduced delay between chunks from 0.5 to 0.1
        except Exception as e:
            print(f"{Fore.RED}Error sending message: {e}{Style.RESET_ALL}")

    async def disconnect(self):
        """Safely disconnect from the BBS."""
        if self.bot.connected:
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
        
        # Use our own disconnect method instead of the bot's
        await self.disconnect()
        
        try:
            self.loop.stop()
        except:
            pass

    def run(self):
        """Main entry point"""
        # Handle Linux signals
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
            self.loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))

        try:
            self.loop.run_until_complete(self.main_loop())
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.loop.close()

def main():
    parser = argparse.ArgumentParser(description='BBS Chatbot CLI')
    parser.add_argument('--host', help='BBS host address')
    parser.add_argument('--port', type=int, help='BBS port number')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI dependencies')
    
    args = parser.parse_args()
    
    print("BBS Chatbot CLI")
    print("---------------")
    
    bot = BBSBotCLI(args)
    bot.run()

if __name__ == "__main__":
    main()
