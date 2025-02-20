import asyncio
import sys
import logging
import argparse
import signal
import importlib.util
import telnetlib3  # Add this import
from colorama import init, Fore, Style
import tkinter as tk  # Add this for creating a dummy root

# Initialize colorama
init()

class BBSBotCLI:
    def __init__(self, args):
        self.setup_logging()
        
        # Import UltronPreAlpha
        spec = importlib.util.spec_from_file_location(
            "UltronPreAlpha", 
            "UltronPreAlpha.py"
        )
        ultron_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ultron_module)
        
        # Create a dummy Tkinter root that won't be shown
        dummy_root = tk.Tk()
        dummy_root.withdraw()  # Hide the window
        
        # Create instance of the original bot with dummy root
        self.bot = ultron_module.BBSBotApp(dummy_root)
        
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

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('bbs_bot.log'),
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
                if command.strip():
                    await self.process_command(command)
            except EOFError:
                break

    async def process_command(self, command):
        """Process user commands"""
        try:
            if command.startswith('!'):
                # Handle built-in commands
                if command.lower() == '!quit':
                    print("Shutting down...")
                    self.stop_event.set()
                    return
                if command.lower() == '!help':
                    print(f"{Fore.CYAN}Available commands: !quit, !help{Style.RESET_ALL}")
                    return
                # Try to use the original bot's command processor if it exists
                if hasattr(self.bot, 'process_command'):
                    await self.bot.process_command(command)
            else:
                # Direct message sending
                await self.send_message(command)
        except Exception as e:
            print(f"{Fore.RED}Error processing command: {e}{Style.RESET_ALL}")

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
                
                # Let the original bot process the data
                if hasattr(self.bot, 'process_data'):
                    await self.bot.process_data(data)

        except Exception as e:
            print(f"{Fore.RED}Error reading from BBS: {e}{Style.RESET_ALL}")
        finally:
            self.stop_event.set()
            self.bot.connected = False

    def run(self):
        """Main entry point"""
        def signal_handler(sig, frame):
            print("\nShutting down gracefully...")
            self.stop_event.set()
            if hasattr(self.bot, 'disconnect'):
                asyncio.run_coroutine_threadsafe(self.bot.disconnect(), self.loop)
            self.loop.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        try:
            self.loop.run_until_complete(self.main_loop())
        except KeyboardInterrupt:
            pass
        finally:
            if self.bot.connected:
                if hasattr(self.bot, 'disconnect'):
                    self.loop.run_until_complete(self.bot.disconnect())
            self.loop.close()

def main():
    parser = argparse.ArgumentParser(description='BBS Chatbot CLI')
    parser.add_argument('--host', help='BBS host address')
    parser.add_argument('--port', type=int, help='BBS port number')
    parser.add_argument('--config', help='Path to config file')
    
    args = parser.parse_args()
    
    print("BBS Chatbot CLI")
    print("---------------")
    
    bot = BBSBotCLI(args)
    bot.run()

if __name__ == "__main__":
    main()
