import asyncio
import telnetlib3
import threading
import queue
import re
import sys
import requests
import openai
import json
import os
import boto3
import time
import logging
import argparse
import signal
import msvcrt
import ctypes
from ctypes import wintypes
from datetime import datetime
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from pytube import YouTube
from pydub import AudioSegment
import subprocess
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
import shlex
from bs4 import BeautifulSoup
from colorama import init, Fore, Back, Style

def enable_windows_ansi():
    """Enable ANSI escape sequences for Windows PowerShell"""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = wintypes.DWORD()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    mode.value |= 4  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    kernel32.SetConsoleMode(handle, mode)

# Initialize colorama and Windows ANSI support
init()
enable_windows_ansi()

class BBSBotCLI:
    def __init__(self, args):
        self.setup_logging()
        self.config = self.load_config(args.config)
        
        # Initialize core settings - will be overridden by prompt if not provided
        self.host = None
        self.port = None
        self.username = args.username or self.config.get('username', '')
        self.password = args.password or self.config.get('password', '')
        self.auto_login = args.auto_login or self.config.get('auto_login', False)
        self.no_spam_mode = args.no_spam or self.config.get('no_spam', False)

        # Get connection details from user if not provided
        if not args.host:
            self.host = input("Enter BBS hostname: ").strip()
        else:
            self.host = args.host

        if not args.port:
            port_str = input("Enter port number [23]: ").strip()
            self.port = int(port_str) if port_str else 23
        else:
            self.port = args.port

        # Initialize API clients and connections
        self.init_api_clients()
        self.init_db_connections()
        
        # Runtime state initialization
        self.connected = False
        self.reader = None
        self.writer = None
        self.msg_queue = queue.Queue()
        self.chat_members = set()
        self.partial_line = ""
        self.stop_event = threading.Event()
        self.keep_alive_stop_event = threading.Event()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Initialize command history
        self.command_history = []
        self.init_readline()

    def setup_logging(self):
        """Configure logging with rotation and levels"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('bbs_bot.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self, config_path):
        """Load and validate configuration file"""
        default_config = {
            'host': 'bbs.example.com',
            'port': 23,
            'api_keys': {},
            'auto_login': False,
            'no_spam': False,
            'commands': {
                'enabled': ['weather', 'chat', 'news'],
                'disabled': []
            }
        }

        if not config_path or not os.path.exists(config_path):
            self.logger.warning("No config file found, using defaults")
            return default_config

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except json.JSONDecodeError:
            self.logger.error("Invalid config file")
            return default_config

    def init_api_clients(self):
        """Initialize API clients from config"""
        api_keys = self.config.get('api_keys', {})
        self.openai_client = OpenAI(api_key=api_keys.get('openai', ''))
        # Initialize other API clients...

    def init_db_connections(self):
        """Initialize database connections"""
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.setup_dynamodb_tables()

    def setup_dynamodb_tables(self):
        """Ensure required DynamoDB tables exist"""
        table_definitions = {
            'ChatBotConversations': {
                'KeySchema': [
                    {'AttributeName': 'username', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'AttributeDefinitions': [
                    {'AttributeName': 'username', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'N'}
                ]
            },
            'PendingMessages': {
                'KeySchema': [
                    {'AttributeName': 'recipient', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'AttributeDefinitions': [
                    {'AttributeName': 'recipient', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'N'}
                ]
            }
        }

        for table_name, definition in table_definitions.items():
            self.create_table_if_not_exists(table_name, definition)

    def create_table_if_not_exists(self, table_name, definition):
        try:
            self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=definition['KeySchema'],
                AttributeDefinitions=definition['AttributeDefinitions'],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            self.logger.info(f"Created table {table_name}")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            self.logger.debug(f"Table {table_name} already exists")

    def init_readline(self):
        """Initialize basic command history and completion"""
        try:
            import readline  # Use built-in readline on Unix-like systems
            readline.set_completer(self.complete)
            readline.parse_and_bind('tab: complete')
        except ImportError:
            try:
                import pyreadline3.rlmain  # For Windows
                import pyreadline3.console
                readline = pyreadline3.rlmain
                readline.set_completer(self.complete)
            except ImportError:
                self.logger.warning("Neither readline nor pyreadline3 available. Tab completion disabled.")
                return

        self.commands = ['!weather', '!chat', '!news', '!help', '!quit']

    def complete(self, text, state):
        """Provide tab completion for commands"""
        matches = [cmd for cmd in self.commands if cmd.startswith(text)]
        return matches[state] if state < len(matches) else None

    async def keep_alive(self):
        """Send periodic keep-alive messages to maintain the connection."""
        while not self.keep_alive_stop_event.is_set() and self.connected:
            try:
                if self.writer:
                    self.writer.write("\r\n")
                    await self.writer.drain()
                    self.logger.debug("Keep-alive sent")
            except Exception as e:
                self.logger.error(f"Keep-alive error: {e}")
                break
            await asyncio.sleep(30)  # Send keep-alive every 30 seconds

    async def connect(self):
        """Establish connection to the BBS with improved error handling"""
        try:
            self.reader, self.writer = await telnetlib3.open_connection(
                host=self.host,
                port=self.port,
                encoding='cp437',
                cols=136,
                term='ansi'  # Explicitly set terminal type to ANSI
            )
            
            # Wait briefly to ensure connection is stable
            await asyncio.sleep(1)
            
            if not self.writer.is_closing():
                self.connected = True
                self.logger.info(f"Connected to {self.host}:{self.port}")
                
                if self.auto_login:
                    await self.handle_auto_login()
                
                return True
            else:
                self.logger.error("Connection closed immediately after establishing")
                return False
                
        except ConnectionRefusedError:
            self.logger.error(f"Connection refused by {self.host}:{self.port}")
            return False
        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            return False

    async def handle_auto_login(self):
        """Handle automatic login sequence if enabled"""
        try:
            await asyncio.sleep(2)  # Wait for login prompt
            
            if self.username:
                await self.send_message(self.username)
                await asyncio.sleep(1)
                
            if self.password:
                await self.send_message(self.password)
                await asyncio.sleep(1)
                
            # Send a few ENTERs to get through any initial screens
            for _ in range(3):
                await self.send_message("")
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Auto-login failed: {e}")

    def display_status(self):
        """Display current connection status and statistics"""
        status = f"""
{Fore.CYAN}=== BBS Bot Status ==={Style.RESET_ALL}
Connection: {'Connected' if self.connected else 'Disconnected'}
Host: {self.host}:{self.port}
Users Online: {len(self.chat_members)}
No-Spam Mode: {'Enabled' if self.no_spam_mode else 'Disabled'}
"""
        print(status)

    def run(self):
        """Main entry point for the CLI application"""
        def signal_handler(sig, frame):
            print("\nShutting down gracefully...")
            self.stop_event.set()
            self.keep_alive_stop_event.set()
            if self.connected:
                asyncio.run_coroutine_threadsafe(self.disconnect(), self.loop)
            sys.exit(0)

        try:
            # Use CTRL_C_EVENT for Windows
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except AttributeError:
            # Some signals might not be available on Windows
            pass

        try:
            self.loop.run_until_complete(self.main_loop())
        except KeyboardInterrupt:
            pass
        finally:
            if self.connected:
                self.loop.run_until_complete(self.disconnect())
            self.loop.close()

    async def main_loop(self):
        """Main application loop"""
        if not await self.connect():
            return

        # Start background tasks
        input_task = asyncio.create_task(self.handle_user_input())
        read_task = asyncio.create_task(self.read_bbs_output())
        keep_alive_task = asyncio.create_task(self.keep_alive())

        try:
            await asyncio.gather(input_task, read_task, keep_alive_task)
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
        if command.startswith('!'):
            await self.handle_command(command)
        else:
            await self.send_message(command)

    async def read_bbs_output(self):
        """Read and process output from the BBS connection with improved handling"""
        try:
            while not self.stop_event.is_set() and self.connected:
                try:
                    data = await asyncio.wait_for(self.reader.read(4096), timeout=60)
                    if not data:
                        print(f"{Fore.RED}Connection closed by server{Style.RESET_ALL}")
                        break
                    
                    # Process the received data
                    print(f"{Fore.WHITE}{data}{Style.RESET_ALL}", end='')
                    sys.stdout.flush()  # Ensure output is displayed immediately
                    
                    # Process any triggers or commands in the data
                    self.process_data_chunk(data)

                except asyncio.TimeoutError:
                    # No data received for 60 seconds, check connection
                    if not self.writer or self.writer.is_closing():
                        print(f"{Fore.RED}Connection lost{Style.RESET_ALL}")
                        break
                    continue

        except Exception as e:
            print(f"{Fore.RED}Error reading from BBS: {e}{Style.RESET_ALL}")
        finally:
            self.connected = False
            self.stop_event.set()  # Signal other tasks to stop

    async def disconnect(self):
        """Disconnect from the BBS server"""
        if self.connected:
            try:
                if self.writer:
                    self.writer.close()
                    await self.writer.wait_closed()
                self.connected = False
                print(f"{Fore.YELLOW}Disconnected from BBS{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error during disconnect: {e}{Style.RESET_ALL}")

    async def send_message(self, message):
        """Send a message to the BBS"""
        if not self.connected:
            print(f"{Fore.RED}Not connected to BBS{Style.RESET_ALL}")
            return
        
        try:
            self.writer.write(f"{message}\r\n")
            await self.writer.drain()
        except Exception as e:
            print(f"{Fore.RED}Error sending message: {e}{Style.RESET_ALL}")

    async def handle_command(self, command):
        """Process CLI commands"""
        cmd = command.lower()
        if cmd == '!quit':
            print("Shutting down...")
            self.stop_event.set()
        elif cmd == '!help':
            print(f"{Fore.CYAN}Available commands: !quit, !help{Style.RESET_ALL}")
        else:
            # Pass the command to the BBS
            await self.send_message(command)

    def process_data_chunk(self, data):
        """Process incoming data chunks"""
        # Accumulate partial lines
        self.partial_line += data
        
        # Split on newlines
        lines = self.partial_line.split('\n')
        
        # Process complete lines
        for line in lines[:-1]:
            self.process_line(line.strip())
        
        # Keep the last partial line
        self.partial_line = lines[-1]

    def process_line(self, line):
        """Process a complete line of BBS output"""
        # Add any specific line processing logic here
        pass

    def get_terminal_width(self):
        """Get the current terminal width for Windows PowerShell"""
        try:

            from ctypes import windll, create_string_buffer
            h = windll.kernel32.GetStdHandle(-11)
            csbi = create_string_buffer(22)
            res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
            if res:
                import struct
                (bufx, bufy, curx, cury, wattr, left, top, right, bottom, maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
                return right - left + 1
            return 80
        except:
            return 80

    def format_output(self, text, width=None):
        """Format output text to fit terminal width"""
        if width is None:
            width = self.get_terminal_width()
        # Add word wrapping logic here
        return text

# ... [Additional methods from the original class, converted to CLI usage] ...

def main():
    parser = argparse.ArgumentParser(description='BBS Chatbot CLI')
    parser.add_argument('--host', help='BBS host address')
    parser.add_argument('--port', type=int, help='BBS port number')
    parser.add_argument('--username', help='BBS username')
    parser.add_argument('--password', help='BBS password')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--auto-login', action='store_true', help='Enable auto login')
    parser.add_argument('--no-spam', action='store_true', help='Enable no spam mode')
    
    args = parser.parse_args()
    
    print("BBS Chatbot CLI")
    print("---------------")
    
    bot = BBSBotCLI(args)
    bot.run()

if __name__ == "__main__":
    main()
