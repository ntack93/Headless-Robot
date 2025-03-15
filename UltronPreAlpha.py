import tkinter as tk
from tkinter import ttk
import threading
import asyncio
import telnetlib3
import time
import queue
import re
import sys
import requests
import openai
import json
import os
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from pytube import YouTube
from pydub import AudioSegment
import subprocess
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
import shlex
from bs4 import BeautifulSoup
import imaplib
import email
from email.utils import parseaddr

# Load API keys from api_keys.json
def load_api_keys():
    if os.path.exists("api_keys.json"):
        with open("api_keys.json", "r") as file:
            return json.load(file)
    return {}

api_keys = load_api_keys()

###############################################################################
# Default/placeholder API keys (updated in Settings window as needed).
###############################################################################
DEFAULT_OPENAI_API_KEY = api_keys.get("openai_api_key", "")
DEFAULT_WEATHER_API_KEY = api_keys.get("weather_api_key", "")
DEFAULT_YOUTUBE_API_KEY = api_keys.get("youtube_api_key", "")
DEFAULT_GOOGLE_CSE_KEY = api_keys.get("google_cse_api_key", "")  # Google Custom Search API Key
DEFAULT_GOOGLE_CSE_CX = api_keys.get("google_cse_cx", "")   # Google Custom Search Engine ID (cx)
DEFAULT_GOOGLE_CSE_PIC_CX = api_keys.get("google_cse_pic_cx", "85aed09b11ea947b1")  # Picture Search Engine ID
DEFAULT_NEWS_API_KEY = api_keys.get("news_api_key", "")    # NewsAPI Key
DEFAULT_GOOGLE_PLACES_API_KEY = api_keys.get("google_places_api_key", "")  # Google Places API Key
DEFAULT_PEXELS_API_KEY = api_keys.get("pexels_api_key", "")  # Pexels API Key
DEFAULT_ALPHA_VANTAGE_API_KEY = api_keys.get("alpha_vantage_api_key", "")  # Alpha Vantage API Key
DEFAULT_COINMARKETCAP_API_KEY = api_keys.get("coinmarketcap_api_key", "")  # CoinMarketCap API Key
DEFAULT_GIPHY_API_KEY = api_keys.get("giphy_api_key", "")  # Add default Giphy API Key

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table_name = 'ChatBotConversations'
table = dynamodb.Table(table_name)

class BBSBotApp:
    def __init__(self, master):
        self.master = master
        self.master.title("BBS Chatbot Jeremy")

        # Load nospam states first
        saved_states = self.load_no_spam_state()
        self.no_spam_mode = tk.BooleanVar(value=saved_states['nospam'])
        self.no_spam_perm = saved_states['nospam_perm']  # Initialize from saved state

        # ----------------- Configurable variables ------------------
        self.host = tk.StringVar(value="bbs.example.com")
        self.port = tk.IntVar(value=23)
        self.openai_api_key = tk.StringVar(value=DEFAULT_OPENAI_API_KEY)
        self.weather_api_key = tk.StringVar(value=DEFAULT_WEATHER_API_KEY)
        self.youtube_api_key = tk.StringVar(value=DEFAULT_YOUTUBE_API_KEY)
        self.google_cse_api_key = tk.StringVar(value=DEFAULT_GOOGLE_CSE_KEY)
        self.google_cse_cx = tk.StringVar(value=DEFAULT_GOOGLE_CSE_CX)  # For search
        self.google_cse_pic_cx = tk.StringVar(value=DEFAULT_GOOGLE_CSE_PIC_CX)  # For pictures
        self.news_api_key = tk.StringVar(value=DEFAULT_NEWS_API_KEY)
        self.google_places_api_key = tk.StringVar(value=DEFAULT_GOOGLE_PLACES_API_KEY)
        self.pexels_api_key = tk.StringVar(value=DEFAULT_PEXELS_API_KEY)  # Ensure Pexels API Key is loaded
        self.nickname = tk.StringVar(value=self.load_nickname())
        self.username = tk.StringVar(value=self.load_username())
        self.password = tk.StringVar(value=self.load_password())
        self.remember_username = tk.BooleanVar(value=False)
        self.remember_password = tk.BooleanVar(value=False)
        self.in_teleconference = False  # Flag to track teleconference state
        self.mud_mode = tk.BooleanVar(value=False)
        self.alpha_vantage_api_key = tk.StringVar(value=DEFAULT_ALPHA_VANTAGE_API_KEY)  # Ensure Alpha Vantage API Key is loaded
        self.coinmarketcap_api_key = tk.StringVar(value=DEFAULT_COINMARKETCAP_API_KEY)  # Ensure CoinMarketCap API Key is loaded
        self.logon_automation_enabled = tk.BooleanVar(value=False)  # Correct initialization
        self.auto_login_enabled = tk.BooleanVar(value=False)  # Add Auto Login toggle
        self.giphy_api_key = tk.StringVar(value=DEFAULT_GIPHY_API_KEY)  # Add Giphy API Key
        self.split_view_enabled = False  # Add Split View toggle
        self.split_view_clones = []  # Track split view clones
        self.public_message_history = {}  # Dictionary to store public messages
        self.multi_line_buffer = {}    # Maps username -> accumulated message string
        self.multiline_timeout = {}    # Maps username -> timeout ID (from after())

        # For best ANSI alignment, recommend a CP437-friendly monospace font:
        self.font_name = tk.StringVar(value="Courier New")
        self.font_size = tk.IntVar(value=10)

        # Terminal mode (ANSI only)
        self.terminal_mode = tk.StringVar(value="ANSI")

        # Telnet references
        self.reader = None
        self.writer = None
        self.stop_event = threading.Event()  # signals background thread to stop
        self.connected = False

        # A queue to pass data from telnet thread => main thread
        self.msg_queue = queue.Queue()

        # A buffer to accumulate partial lines
        self.partial_line = ""
        self.partial_message = ""  # Buffer to accumulate partial messages

        self.favorites = self.load_favorites()  # Load favorite BBS addresses
        self.favorites_window = None  # Track the Favorites window instance

        self.chat_members = set()  # Set to keep track of chat members
        self.last_seen = self.load_last_seen()  # Load last seen timestamps from file
        self.last_spoke = self.load_last_spoke()  # Load last spoke timestamps from file

        # Build UI
        self.build_ui()

        # Periodically check for incoming messages
        self.master.after(100, self.process_incoming_messages)

        self.keep_alive_stop_event = threading.Event()
        self.keep_alive_task = None
        self.loop = asyncio.new_event_loop()  # Initialize loop attribute
        asyncio.set_event_loop(self.loop)  # Set the event loop

        self.dynamodb_client = boto3.client('dynamodb', region_name='us-east-1')
        self.table_name = table_name
        self.create_dynamodb_table()
        self.previous_line = ""  # Store the previous line to detect multi-line triggers
        self.user_list_buffer = []  # Buffer to accumulate user list lines
        self.timers = {}  # Dictionary to store active timers
        self.auto_greeting_enabled = False  # Default auto-greeting to off
        self.pending_messages_table_name = 'PendingMessages'
        self.create_pending_messages_table()
        self.openai_client = OpenAI(api_key=self.openai_api_key.get())
        self.in_teleconference = False  # Add this flag
        self.join_timer = None  # Add timer reference
        
        # Start checking for incoming emails
        self.master.after(10000, self.check_incoming_mail)  # Start checking after 10 seconds




    def create_dynamodb_table(self):
        """Create DynamoDB table if it doesn't exist."""
        try:
            self.dynamodb_client.describe_table(TableName=self.table_name)
        except self.dynamodb_client.exceptions.ResourceNotFoundException:
            self.dynamodb_client.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {'AttributeName': 'username', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'username', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'N'}
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            self.dynamodb_client.get_waiter('table_exists').wait(TableName=self.table_name)

    def create_pending_messages_table(self):
        """Create DynamoDB table for pending messages if it doesn't exist."""
        try:
            self.dynamodb_client.describe_table(TableName=self.pending_messages_table_name)
        except self.dynamodb_client.exceptions.ResourceNotFoundException:
            self.dynamodb_client.create_table(
                TableName=self.pending_messages_table_name,
                KeySchema=[
                    {'AttributeName': 'recipient', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'recipient', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'N'}
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            self.dynamodb_client.get_waiter('table_exists').wait(TableName=self.pending_messages_table_name)

    def save_conversation(self, username, message, response):
        """Save conversation to DynamoDB."""
        timestamp = int(time.time())
        # Ensure the response is split into chunks of 250 characters
        response_chunks = self.chunk_message(response, 250)
        for chunk in response_chunks:
            table.put_item(
                Item={
                    'username': username,
                    'timestamp': timestamp,
                    'message': message,
                    'response': chunk
                }
            )
            # Update the timestamp for each chunk to maintain order
            timestamp += 1

    def get_conversation_history(self, username):
        """Retrieve conversation history from DynamoDB."""
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('username').eq(username)
        )
        items = response.get('Items', [])
        # Combine response chunks into full responses
        conversation_history = []
        current_response = ""
        for item in items:
            current_response += item['response']
            if len(current_response) >= 250:
                conversation_history.append({
                    'message': item['message'],
                    'response': current_response
                })
                current_response = ""
        if current_response:
            conversation_history.append({
                'message': items[-1]['message'],
                'response': current_response
            })
        return conversation_history

    def save_pending_message(self, recipient, sender, message):
        """Save a pending message to DynamoDB."""
        timestamp = int(time.time())
        pending_messages_table = dynamodb.Table(self.pending_messages_table_name)
        pending_messages_table.put_item(
            Item={
                'recipient': recipient.lower(),
                'timestamp': timestamp,
                'sender': sender,
                'message': message
            }
        )

    def get_pending_messages(self, recipient):
        """Retrieve pending messages for a recipient from DynamoDB."""
        pending_messages_table = dynamodb.Table(self.pending_messages_table_name)
        response = pending_messages_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('recipient').eq(recipient.lower())
        )
        return response.get('Items', [])

    def delete_pending_message(self, recipient, timestamp):
        """Delete a pending message from DynamoDB."""
        pending_messages_table = dynamodb.Table(self.pending_messages_table_name)
        pending_messages_table.delete_item(
            Key={
                'recipient': recipient.lower(),
                'timestamp': timestamp
            }
        )

    def build_ui(self):
        """Set up frames, text areas, input boxes, etc."""
        main_frame = ttk.Frame(self.master, name='main_frame')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ----- Config frame -----
        config_frame = ttk.LabelFrame(main_frame, text="Connection Settings")
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(config_frame, text="BBS Host:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        self.host_entry = ttk.Entry(config_frame, textvariable=self.host, width=30)
        self.host_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        self.create_context_menu(self.host_entry)

        ttk.Label(config_frame, text="Port:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)
        self.port_entry = ttk.Entry(config_frame, textvariable=self.port, width=6)
        self.port_entry.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)
        self.create_context_menu(self.port_entry)

        self.connect_button = ttk.Button(config_frame, text="Connect", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=4, padx=5, pady=5)

        # Add a "Settings" button
        settings_button = ttk.Button(config_frame, text="Settings", command=self.show_settings_window)
        settings_button.grid(row=0, column=5, padx=5, pady=5)

        # Add a "Favorites" button
        favorites_button = ttk.Button(config_frame, text="Favorites", command=self.show_favorites_window)
        favorites_button.grid(row=0, column=6, padx=5, pady=5)

        # Add a "Mud Mode" checkbox
        mud_mode_check = ttk.Checkbutton(config_frame, text="Mud Mode", variable=self.mud_mode)
        mud_mode_check.grid(row=0, column=7, padx=5, pady=5)

        # Add a "Split View" button
        split_view_button = ttk.Button(config_frame, text="Split View", command=self.toggle_split_view)
        split_view_button.grid(row=0, column=8, padx=5, pady=5)

        # Add a "Teleconference" button
        teleconference_button = ttk.Button(config_frame, text="Teleconference", command=self.send_teleconference_command)
        teleconference_button.grid(row=0, column=9, padx=5, pady=5)

        # ----- Username frame -----
        username_frame = ttk.LabelFrame(main_frame, text="Username")
        username_frame.pack(fill=tk.X, padx=5, pady=5)

        self.username_entry = ttk.Entry(username_frame, textvariable=self.username, width=30)
        self.username_entry.pack(side=tk.LEFT, padx=5, pady=5)
        self.create_context_menu(self.username_entry)

        self.remember_username_check = ttk.Checkbutton(username_frame, text="Remember", variable=self.remember_username)
        self.remember_username_check.pack(side=tk.LEFT, padx=5, pady=5)

        self.send_username_button = ttk.Button(username_frame, text="Send", command=self.send_username)
        self.send_username_button.pack(side=tk.LEFT, padx=5, pady=5)

        # ----- Password frame -----
        password_frame = ttk.LabelFrame(main_frame, text="Password")
        password_frame.pack(fill=tk.X, padx=5, pady=5)

        self.password_entry = ttk.Entry(password_frame, textvariable=self.password, width=30, show="*")
        self.password_entry.pack(side=tk.LEFT, padx=5, pady=5)
        self.create_context_menu(self.password_entry)

        self.remember_password_check = ttk.Checkbutton(password_frame, text="Remember", variable=self.remember_password)
        self.remember_password_check.pack(side=tk.LEFT, padx=5, pady=5)

        self.send_password_button = ttk.Button(password_frame, text="Send", command=self.send_password)
        self.send_password_button.pack(side=tk.LEFT, padx=5, pady=5)

        # ----- Terminal output -----
        terminal_frame = ttk.LabelFrame(main_frame, text="BBS Output")
        terminal_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.terminal_display = tk.Text(
            terminal_frame,
            wrap=tk.WORD,
            height=15,
            state=tk.NORMAL,
            bg="black"
        )
        self.terminal_display.configure(state=tk.DISABLED)
        self.terminal_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_bar = ttk.Scrollbar(terminal_frame, command=self.terminal_display.yview)
        scroll_bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.terminal_display.configure(yscrollcommand=scroll_bar.set)

        self.define_ansi_tags()

        # ----- Input frame -----
        input_frame = ttk.LabelFrame(main_frame, text="Send Message")
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.input_var = tk.StringVar()
        self.input_box = ttk.Entry(input_frame, textvariable=self.input_var, width=80)
        self.input_box.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        self.input_box.bind("<Return>", self.send_message)
        self.create_context_menu(self.input_box)

        self.send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Set initial font
        self.update_display_font()

    def create_context_menu(self, widget):
        """Create a right-click context menu for the given widget."""
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="Select All", command=lambda: widget.event_generate("<<SelectAll>>"))

        def show_context_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_context_menu)

    def show_settings_window(self):
        """Open a Toplevel with fields for API keys, font settings, etc."""
        settings_win = tk.Toplevel(self.master)
        settings_win.title("Settings")

        row_index = 0

        # ----- OpenAI API Key -----
        ttk.Label(settings_win, text="OpenAI API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        openai_api_key_entry = ttk.Entry(settings_win, textvariable=self.openai_api_key, width=40)
        openai_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(openai_api_key_entry)
        row_index += 1

        # ----- Weather API Key -----
        ttk.Label(settings_win, text="Weather API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        weather_api_key_entry = ttk.Entry(settings_win, textvariable=self.weather_api_key, width=40)
        weather_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(weather_api_key_entry)
        row_index += 1

        # ----- YouTube API Key -----
        ttk.Label(settings_win, text="YouTube API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        youtube_api_key_entry = ttk.Entry(settings_win, textvariable=self.youtube_api_key, width=40)
        youtube_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(youtube_api_key_entry)
        row_index += 1

        # ----- Google CSE Key -----
        ttk.Label(settings_win, text="Google CSE API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        google_cse_api_key_entry = ttk.Entry(settings_win, textvariable=self.google_cse_api_key, width=40)
        google_cse_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(google_cse_api_key_entry)
        row_index += 1

        # ----- Google CSE ID (search) -----
        ttk.Label(settings_win, text="Google CSE ID (search):").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        google_cse_cx_entry = ttk.Entry(settings_win, textvariable=self.google_cse_cx, width=40)
        google_cse_cx_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(google_cse_cx_entry)
        row_index += 1

        # ----- Google CSE ID (pictures) -----
        ttk.Label(settings_win, text="Google CSE ID (pictures):").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        google_cse_pic_cx_entry = ttk.Entry(settings_win, textvariable=self.google_cse_pic_cx, width=40)
        google_cse_pic_cx_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(google_cse_pic_cx_entry)
        row_index += 1

        # ----- News API Key -----
        ttk.Label(settings_win, text="News API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        news_api_key_entry = ttk.Entry(settings_win, textvariable=self.news_api_key, width=40)
        news_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(news_api_key_entry)
        row_index += 1

        # ----- Google Places API Key -----
        ttk.Label(settings_win, text="Google Places API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        google_places_api_key_entry = ttk.Entry(settings_win, textvariable=self.google_places_api_key, width=40)
        google_places_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(google_places_api_key_entry)
        row_index += 1

        # ----- Pexels API Key -----
        ttk.Label(settings_win, text="Pexels API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        pexels_api_key_entry = ttk.Entry(settings_win, textvariable=self.pexels_api_key, width=40)
        pexels_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(pexels_api_key_entry)
        row_index += 1

        # ----- Alpha Vantage API Key -----
        ttk.Label(settings_win, text="Alpha Vantage API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        alpha_vantage_api_key_entry = ttk.Entry(settings_win, textvariable=self.alpha_vantage_api_key, width=40)
        alpha_vantage_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(alpha_vantage_api_key_entry)
        row_index += 1

        # ----- CoinMarketCap API Key -----
        ttk.Label(settings_win, text="CoinMarketCap API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        coinmarketcap_api_key_entry = ttk.Entry(settings_win, textvariable=self.coinmarketcap_api_key, width=40)
        coinmarketcap_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(coinmarketcap_api_key_entry)
        row_index += 1

        # ----- Giphy API Key -----
        ttk.Label(settings_win, text="Giphy API Key:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        giphy_api_key_entry = ttk.Entry(settings_win, textvariable=self.giphy_api_key, width=40)
        giphy_api_key_entry.grid(row=row_index, column=1, padx=5, pady=5)
        self.create_context_menu(giphy_api_key_entry)
        row_index += 1

        # ----- Font Name -----
        ttk.Label(settings_win, text="Font Name:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        font_options = ["Courier New", "Px437 IBM VGA8", "Terminus (TTF)", "Consolas", "Lucida Console"]
        font_dropdown = ttk.Combobox(settings_win, textvariable=self.font_name, values=font_options, state="readonly")
        font_dropdown.grid(row=row_index, column=1, padx=5, pady=5, sticky=tk.W)
        row_index += 1

        # ----- Font Size -----
        ttk.Label(settings_win, text="Font Size:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        ttk.Entry(settings_win, textvariable=self.font_size, width=5).grid(row=row_index, column=1, padx=5, pady=5, sticky=tk.W)
        row_index += 1

        # Info label about recommended fonts
        info_label = ttk.Label(
            settings_win,
            text=(
                "Tip: For best ANSI alignment, install a CP437-compatible\n"
                "monospace font like 'Px437 IBM VGA8' or 'Terminus (TTF)'.\n"
                "Then select its name from the Font Name dropdown."
            )
        )
        info_label.grid(row=row_index, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        row_index += 1

        # Add Mud Mode checkbox
        ttk.Label(settings_win, text="Mud Mode:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        ttk.Checkbutton(settings_win, variable=self.mud_mode).grid(row=row_index, column=1, padx=5, pady=5, sticky=tk.W)
        row_index += 1

        # Add Logon Automation checkbox
        ttk.Label(settings_win, text="Logon Automation:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        ttk.Checkbutton(settings_win, variable=self.logon_automation_enabled).grid(row=row_index, column=1, padx=5, pady=5, sticky=tk.W)
        row_index += 1

        # Add Auto Login checkbox
        ttk.Label(settings_win, text="Auto Login:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        ttk.Checkbutton(settings_win, variable=self.auto_login_enabled).grid(row=row_index, column=1, padx=5, pady=5, sticky=tk.W)
        row_index += 1

        # Add No Spam Mode checkbox
        ttk.Label(settings_win, text="No Spam Mode:").grid(row=row_index, column=0, padx=5, pady=5, sticky=tk.E)
        ttk.Checkbutton(settings_win, variable=self.no_spam_mode).grid(row=row_index, column=1, padx=5, pady=5, sticky=tk.W)
        row_index += 1

        # ----- Save Button -----
        save_button = ttk.Button(settings_win, text="Save", command=lambda: self.save_settings(settings_win))
        save_button.grid(row=row_index, column=0, columnspan=2, pady=10)

    def save_settings(self, window):
        """Called when user clicks 'Save' in the settings window."""
        self.update_display_font()
        self.openai_client = OpenAI(api_key=self.openai_api_key.get())
        # Save new API keys
        self.save_api_keys()
        window.destroy()

    def save_api_keys(self):
        """Save API keys to a file."""
        api_keys = {
            "openai_api_key": self.openai_api_key.get(),
            "weather_api_key": self.weather_api_key.get(),
            "youtube_api_key": self.youtube_api_key.get(),
            "google_cse_api_key": self.google_cse_api_key.get(),
            "google_cse_cx": self.google_cse_cx.get(),
            "google_cse_pic_cx": self.google_cse_pic_cx.get(),
            "news_api_key": self.news_api_key.get(),
            "google_places_api_key": self.google_places_api_key.get(),
            "pexels_api_key": self.pexels_api_key.get(),
            "alpha_vantage_api_key": self.alpha_vantage_api_key.get(),
            "coinmarketcap_api_key": self.coinmarketcap_api_key.get(),
            "giphy_api_key": self.giphy_api_key.get()  # Save Giphy API Key
        }
        with open("api_keys.json", "w") as file:
            json.dump(api_keys, file)

    def load_api_keys(self):
        """Load API keys from a file."""
        if os.path.exists("api_keys.json"):
            with open("api_keys.json", "r") as file:
                api_keys = json.load(file)
                self.openai_api_key.set(api_keys.get("openai_api_key", ""))
                self.weather_api_key.set(api_keys.get("weather_api_key", ""))
                self.youtube_api_key.set(api_keys.get("youtube_api_key", ""))
                self.google_cse_api_key.set(api_keys.get("google_cse_api_key", ""))
                self.google_cse_cx.set(api_keys.get("google_cse_cx", ""))
                self.google_cse_pic_cx.set(api_keys.get("google_cse_pic_cx", ""))
                self.news_api_key.set(api_keys.get("news_api_key", ""))
                self.google_places_api_key.set(api_keys.get("google_places_api_key", ""))
                self.pexels_api_key.set(api_keys.get("pexels_api_key", ""))  # Ensure Pexels API Key is loaded
                self.alpha_vantage_api_key.set(api_keys.get("alpha_vantage_api_key", ""))  # Ensure Alpha Vantage API Key is loaded
                self.coinmarketcap_api_key.set(api_keys.get("coinmarketcap_api_key", ""))  # Ensure CoinMarketCap API Key is loaded
                self.giphy_api_key.set(api_keys.get("giphy_api_key", ""))  # Ensure Giphy API Key is loaded

    def update_display_font(self):
        """Update the Text widget's font based on self.font_name and self.font_size."""
        new_font = (self.font_name.get(), self.font_size.get())
        self.terminal_display.configure(font=new_font)

    def define_ansi_tags(self):
        """Define text tags for basic ANSI foreground colors (30-37, 90-97)."""
        self.terminal_display.tag_configure("normal", foreground="white")

        color_map = {
            '30': 'black',
            '31': 'red',
            '32': 'green',
            '33': 'yellow',
            '34': 'blue',
            '35': 'magenta',
            '36': 'cyan',
            '37': 'white',
            '90': 'bright_black',
            '91': 'bright_red',
            '92': 'bright_green',
            '93': 'bright_yellow',
            '94': 'bright_blue',
            '95': 'bright_magenta',
            '96': 'bright_cyan',
            '97': 'bright_white'
        }
        for code, color_name in color_map.items():
            if color_name.startswith("bright_"):
                base_color = color_name.split("_", 1)[1]
                self.terminal_display.tag_configure(color_name, foreground=base_color)
            else:
                self.terminal_display.tag_configure(color_name, foreground=color_name)

    def toggle_connection(self):
        """Connect or disconnect from the BBS."""
        if self.connected:
            asyncio.run_coroutine_threadsafe(self.disconnect_from_bbs(), self.loop).result()
        else:
            self.start_connection()

    def connect_to_bbs(self, address):
        """Connect to the BBS with the given address."""
        self.host.set(address)
        self.start_connection()

    def start_connection(self):
        """Start the telnetlib3 client in a background thread."""
        host = self.host.get()
        port = self.port.get()
        self.stop_event.clear()

        def run_telnet():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.telnet_client_task(host, port))

        thread = threading.Thread(target=run_telnet, daemon=True)
        thread.start()
        self.append_terminal_text(f"Connecting to {host}:{port}...\n", "normal")
        self.start_keep_alive()  # Start keep-alive coroutine

    async def telnet_client_task(self, host, port):
        """Async function connecting via telnetlib3 (CP437 + ANSI), reading bigger chunks."""
        try:
            reader, writer = await telnetlib3.open_connection(
                host=host,
                port=port,
                term=self.terminal_mode.get().lower(),
                encoding='cp437',
                cols=136  # Set terminal width to 136 columns
            )
        except Exception as e:
            self.msg_queue.put_nowait(f"Connection failed: {e}\n")
            return

        self.reader = reader
        self.writer = writer
        self.connected = True
        self.connect_button.config(text="Disconnect")
        self.msg_queue.put_nowait(f"Connected to {host}:{port}\n")

        try:
            while not self.stop_event.is_set():
                data = await reader.read(4096)
                if not data:
                    break
                self.msg_queue.put_nowait(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.msg_queue.put_nowait(f"Error reading from server: {e}\n")
        finally:
            await self.disconnect_from_bbs()

    def auto_login_sequence(self):
        """Automate the login sequence."""
        if self.connected and self.writer:
            self.send_username()
            self.master.after(1000, self.send_password)
            self.master.after(2000, self.press_enter_repeatedly, 5)

    def press_enter_repeatedly(self, count):
        """Press ENTER every 1 second for a specified number of times."""
        if self.connected and self.writer:
            if count > 0:
                self.send_enter_keystroke()
                self.master.after(1000, self.press_enter_repeatedly, count - 1)
            else:
                self.master.after(1000, self.send_teleconference_command)

    def send_teleconference_command(self):
        """Send '/go Wordldlink', wait 0.5 seconds, and then send 'ENTER'."""
        if self.connected and self.writer:
            asyncio.run_coroutine_threadsafe(self._send_message('/go tele'), self.loop)
            self.master.after(500, lambda: asyncio.run_coroutine_threadsafe(self._send_message('\r\n'), self.loop))

    async def disconnect_from_bbs(self):
        """Stop the background thread and close connections."""
        if not self.connected:
            return

        self.stop_join_timer()  # Stop join timer on disconnect
        self.in_teleconference = False  # Reset teleconference state
        self.stop_event.set()
        self.stop_keep_alive()  # Stop keep-alive coroutine
        if self.writer:
            try:
                self.writer.close()
                await self.writer.drain()  # Ensure the writer is closed properly
            except Exception as e:
                print(f"Error closing writer: {e}")
        else:
            print("Writer is already None")

        self.connected = False
        self.reader = None
        self.writer = None

        def update_connect_button():
            try:
                if self.connect_button and self.connect_button.winfo_exists():
                    self.connect_button.config(text="Connect")
            except tk.TclError:
                pass

        # Schedule the update_connect_button call from the main thread
        if threading.current_thread() is threading.main_thread():
            update_connect_button()
        else:
            try:
                self.master.after_idle(update_connect_button)
            except RuntimeError as e:
                print(f"Error scheduling update_connect_button: {e}")
        self.msg_queue.put_nowait("Disconnected from BBS.\n")

    def process_incoming_messages(self):
        """Check the queue for data, parse lines, schedule next check."""
        try:
            while True:
                data = self.msg_queue.get_nowait()
                print(f"Incoming message: {data}")  # Log incoming messages
                self.process_data_chunk(data)
        except queue.Empty:
            pass
        finally:
            self.master.after(100, self.process_incoming_messages)

    def process_data_chunk(self, data):
        """Process incoming data and handle triggers."""
        data = data.replace('\r\n', '\n').replace('\r', '\n')
        self.partial_line += data
        lines = self.partial_line.split("\n")
        self.partial_line = lines[-1]  # Keep the last partial line

        for line in lines[:-1]:
            self.append_terminal_text(line + "\n", "normal")
            
            # Remove ANSI codes for easier parsing
            ansi_escape_regex = re.compile(r'\x1b\[(.*?)m')
            clean_line = ansi_escape_regex.sub('', line)

            # Update last seen and last spoke timestamps for any user activity
            public_message_match = re.match(r'From (.+?): (.+)', clean_line)
            whisper_match = re.match(r'From (.+?) \(whispered\): (.+)', clean_line)
            direct_match = re.match(r'From (.+?) \(to you\): (.+)', clean_line)
            page_match = re.match(r'(.+?) is paging you from (.+?): (.+)', clean_line)

            current_time = int(time.time())
            
            # Update timestamps for any type of message
            if public_message_match:
                username = public_message_match.group(1)
                base_username = username.split('@')[0]
                self.last_seen[base_username.lower()] = current_time
                self.last_spoke[base_username.lower()] = current_time
            elif whisper_match:
                username = whisper_match.group(1)
                base_username = username.split('@')[0]
                self.last_seen[base_username.lower()] = current_time
                self.last_spoke[base_username.lower()] = current_time
            elif direct_match:
                username = direct_match.group(1)
                base_username = username.split('@')[0]
                self.last_seen[base_username.lower()] = current_time
                self.last_spoke[base_username.lower()] = current_time
            elif page_match:
                username = page_match.group(1)
                base_username = username.split('@')[0]
                self.last_seen[base_username.lower()] = current_time
                self.last_spoke[base_username.lower()] = current_time

            # Save timestamps after any updates
            if any([public_message_match, whisper_match, direct_match, page_match]):
                self.save_last_seen()
                self.save_last_spoke()

            # Check for private commands first 
            private_message_match = re.match(r'From (.+?) \(whispered\): (.+)', clean_line)
            if private_message_match:
                username = private_message_match.group(1)
                message = private_message_match.group(2)

                # Handle !nospamperm and !nospam via whisper only
                if message.strip() in ["!nospamperm", "!nospam"]:
                    self.handle_private_trigger(username, message)
                    continue

            # Parse message for normal processing
            msg_type, username, content = self.parse_message(clean_line)
            if msg_type and username and content:
                # Ignore messages from Ultron itself
                if username.lower() == 'ultron':
                    continue
                    
                # Handle !nospam command when sent publicly by responding via whisper
                if content.strip() == "!nospam":
                    self.handle_private_trigger(username, content)
                    continue
                    
                # Regular message handling
                if msg_type == 'page':
                    if content.startswith('!'):
                        response = self.get_command_response(content, username)
                    else:
                        response = self.get_chatgpt_response(content, username=username)
                    if response:
                        self.send_page_response(username, 'teleconference', response)
                    
                elif msg_type == 'whisper':
                    if content.startswith('!'):
                        response = self.get_command_response(content, username)
                    else:
                        response = self.get_chatgpt_response(content, username=username)
                    if response:
                        self.send_private_message(username, response)
                    
                elif msg_type == 'direct':
                    if content.startswith('!'):
                        response = self.get_command_response(content, username)
                    else:
                        response = self.get_chatgpt_response(content, username=username)
                    if response:
                        if self.no_spam_mode.get() or self.no_spam_perm:
                            self.send_private_message(username, response)
                        else:
                            self.send_direct_message(username, response)
                        
                elif msg_type == 'public' and content.startswith('!'):
                    response = self.get_command_response(content, username)
                    if response:
                        if self.no_spam_mode.get() or self.no_spam_perm:
                            self.send_private_message(username, response)
                        else:
                            self.send_full_message(response)

            # Update last spoke timestamp for public messages
            public_trigger_match = re.match(r'From (.+?): (.+)', clean_line)
            if public_trigger_match:
                username = public_trigger_match.group(1)
                base_username = username.split('@')[0]  # Strip domain part
                self.last_spoke[base_username.lower()] = int(time.time())
                self.save_last_spoke()

    def update_chat_members(self, lines_with_users):
        """
        Parse user list from the topic/banner message, handling both single and multi-line formats.
        Updates chat members list and last seen timestamps.
        """
        # Join all lines and normalize whitespace
        combined = " ".join(line.strip() for line in lines_with_users.split('\n'))
        print(f"[DEBUG] Combined user lines: {combined}")

        # Remove ANSI codes
        ansi_escape_regex = re.compile(r'\x1b\[(.*?)m')
        combined_clean = ansi_escape_regex.sub('', combined)
        print(f"[DEBUG] Cleaned combined user lines: {combined_clean}")

        # Extract user section between Topic and "are here with you"
        user_list_match = re.search(r'Topic:.*?\)\.\s*(.*?)\s*(?:are|is)\s+here with you', combined_clean, re.DOTALL)
        if not user_list_match:
            print("[DEBUG] Could not find user list section")
            return

        user_section = user_list_match.group(1)
        print(f"[DEBUG] User section: {user_section}")

        # Split users by comma and handle 'and' conjunction
        user_parts = user_section.replace(" and ", ", ").split(",")
        
        # Process each user entry
        usernames = []
        for part in user_parts:
            clean_part = part.strip()
            if clean_part:
                # Extract username from email-style address
                username = clean_part.split('@')[0]
                if username:
                    username = username.strip()  # Remove any whitespace
                    usernames.append(username)
                    # Update last seen timestamp for this user
                    print(f"[DEBUG] Updating last seen for: {username}")
                    self.last_seen[username.lower()] = int(time.time())

        print(f"[DEBUG] Extracted usernames with timestamps: {usernames}")

        # Update chat members set
        self.chat_members = set(usernames)
        self.save_chat_members()

        # Save updated last seen timestamps
        self.save_last_seen()
        print(f"[DEBUG] Updated last seen timestamps: {self.last_seen}")

        # Check for pending messages
        for username in usernames:
            self.check_and_send_pending_messages(username)

    def save_chat_members(self):
        """Save chat members to DynamoDB."""
        chat_members_table = dynamodb.Table('ChatRoomMembers')
        try:
            chat_members_table.put_item(
                Item={
                    'room': 'default',
                    'members': list(self.chat_members)
                }
            )
            print(f"[DEBUG] Saved chat members to DynamoDB: {self.chat_members}")
        except Exception as e:
            print(f"Error saving chat members to DynamoDB: {e}")

    def get_chat_members(self):
        """Retrieve chat members from DynamoDB."""
        chat_members_table = dynamodb.Table('ChatRoomMembers')
        try:
            response = chat_members_table.get_item(Key={'room': 'default'})
            members = response.get('Item', {}).get('members', [])
            print(f"[DEBUG] Retrieved chat members from DynamoDB: {members}")
            return members
        except Exception as e:
            print(f"Error retrieving chat members from DynamoDB: {e}")
            return []

    
        """
        Check for commands in the given line: !weather, !yt, !search, !chat, !news, !map, !pic, !polly, !mp3yt, !help, !seen, !greeting, !stocks, !crypto, !timer, !gif, !msg, !nospam
        And now also capture public messages for conversation history.
        """
        # Remove ANSI codes for easier parsing
        ansi_escape_regex = re.compile(r'\x1b\[(.*?)m')
        clean_line = ansi_escape_regex.sub('', line)

        # Handle !nospam toggle first, so you can always toggle it
        if "!nospam" in clean_line:
            self.no_spam_mode.set(not self.no_spam_mode.get())
            state = "enabled" if self.no_spam_mode.get() else "disabled"
            self.send_full_message(f"No Spam Mode has been {state}.")
            return

        # Check if the message is private
        private_message_match = re.match(r'From (.+?) \(whispered\): (.+)', clean_line)
        page_message_match = re.match(r'(.+?) is paging you (from|via) (.+?): (.+)', clean_line)
        direct_message_match = re.match(r'From (.+?) \(to you\): (.+)', clean_line)

        # Ignore other public messages if no_spam_mode is enabled
        if self.no_spam_mode.get() and not private_message_match and not page_message_match and not direct_message_match:
            return

        # Check for private messages
        if private_message_match:
            username = private_message_match.group(1)
            message = private_message_match.group(2)
            self.partial_message += message + " "
            if message.endswith("."):
                self.handle_private_trigger(username, self.partial_message.strip())
                self.partial_message = ""
            return

        # Check for page commands (both 'from' and 'via')
        if page_message_match:
            username = page_message_match.group(1)
            module_or_channel = page_message_match.group(3)
            message = page_message_match.group(4)
            self._trigger(username, module_or_channel, message)
            return

        # Check for direct messages
        if direct_message_match:
            username = direct_message_match.group(1)
            message = direct_message_match.group(2)
            self.partial_message += message + " "
            if message.endswith("."):
                self.handle_chatgpt_command(self.partial_message.strip(), username=username)
                self.partial_message = ""
            return

        # Check for public triggers
        public_trigger_match = re.match(r'From (.+?): (.+)', clean_line)
        if public_trigger_match:
            username = public_trigger_match.group(1)
            message = public_trigger_match.group(2)
            if self.no_spam_mode.get():
                self.append_terminal_text(f"Ignored public trigger due to No Spam Mode: {message}\n", "normal")
                return
            if message.startswith("!"):
                self.handle_public_trigger(username, message)

        # Check for user-specific triggers
        if self.previous_line == ":***" and clean_line.startswith("->"):
            entrance_message = clean_line[3:].strip()
            self.handle_user_greeting(entrance_message)
        elif re.match(r'(.+?) just joined this channel!', clean_line):
            username = re.match(r'(.+?) just joined this channel!', clean_line).group(1)
            self.handle_user_greeting(username)
        elif re.match(r'(.+?)@(.+?) just joined this channel!', clean_line):
            username = re.match(r'(.+?)@(.+?) just joined this channel!', clean_line).group(1)
            self.handle_user_greeting(username)
        elif re.match(r'Topic: \(.*?\)\.\s*(.*?)\s*are here with you\.', clean_line, re.DOTALL):
            self.update_chat_members(clean_line)
        elif re.match(r'(.+?)@(.+?) \(.*?\) is now online\.  Total users: \d+\.', clean_line):
            # This line indicates a user logged onto the BBS, not necessarily entered the chatroom
            return

        # Check for re-logon automation triggers
        if "please finish up and log off." in clean_line.lower():
            self.handle_cleanup_maintenance()
        if self.auto_login_enabled.get() or self.logon_automation_enabled.get():
            if 'otherwise type "new": ' in clean_line.lower() or 'type it in and press enter' in clean_line.lower():
                self.send_username()
            elif 'enter your password: ' in clean_line.lower():
                self.send_password()
            elif 'if you already have a user-id on this system, type it in and press enter. otherwise type "new":' in clean_line.lower():
                self.send_username()
            elif 'greetings, ' in clean_line.lower() and 'glad to see you back again.' in clean_line.lower():
                self.master.after(1000, self.send_teleconference_command)
        elif '(n)onstop, (q)uit, or (c)ontinue?' in clean_line.lower():
            self.send_enter_keystroke()

# Update the previous line
        self.previous_line = clean_line

    def send_enter_keystroke(self):
        """Send an <ENTER> keystroke to get the list of current chat members."""
        if self.connected and self.writer:
            asyncio.run_coroutine_threadsafe(self._send_message("\r\n"), self.loop)

    def handle_private_trigger(self, username, message):
        """Handle private message triggers and respond privately."""
        message = message.strip()
        
        # Handle nospamperm command
        if message == "!nospamperm":
            self.no_spam_perm = not self.no_spam_perm
            state = "permanently enabled" if self.no_spam_perm else "disabled"
            self.send_private_message(username, f"No Spam Mode has been {state}.")
            self.save_no_spam_state()
            return

        # Handle nospam command
        if message == "!nospam":
            if self.no_spam_perm:
                self.send_private_message(username, "Not possible - No Spam Mode is permanently locked.")
            else:
                self.no_spam_mode.set(not self.no_spam_mode.get())
                state = "enabled" if self.no_spam_mode.get() else "disabled"
                self.send_private_message(username, f"No Spam Mode has been {state}.")
                self.save_no_spam_state()
            return

        # Extract command and query for other commands
        parts = message.strip().split(maxsplit=1)
        command = parts[0].lower()
        query = parts[1] if len(parts) > 1 else ""

        # Handle !msg command with proper whispering
        if command == "!msg":
            msg_parts = query.split(maxsplit=1)
            if len(msg_parts) < 2:
                self.send_private_message(username, "Usage: !msg <username> <message>")
                return
            recipient, msg_content = msg_parts
            self.save_pending_message(recipient, username, msg_content)
            self.send_private_message(username, f"Message for {recipient} saved. They will receive it when next seen.")
            return

        # Handle !trump command
        elif command == "!trump":
            response = self.get_trump_post()
            chunks = self.chunk_message(response, 250)
            for chunk in chunks:
                self.send_private_message(username, chunk)
            return

        # Handle !nospamperm command (whisper only)
        if command == "!nospamperm":
            self.no_spam_perm = not self.no_spam_perm
            state = "permanently enabled" if self.no_spam_perm else "disabled"
            self.send_private_message(username, f"No Spam Permanent Lock has been {state}.")
            return

        # Handle !seen command
        elif command == "!seen":
            if not query:
                self.send_private_message(username, "Usage: !seen <username>")
                return
            response = self.get_seen_response(query)
            self.send_private_message(username, response)
            return

        # Handle !polly command
        elif command == "!polly":
            parts = query.split(maxsplit=1)
            if len(parts) < 2:
                self.send_private_message(username, "Usage: !polly <voice> <text> - Voices are Ruth, Joanna, Danielle, Matthew, Stephen")
                return
            voice, text = parts
            self.handle_polly_command(voice, text)
            return

        # Handle !mp3yt command
        elif command == "!mp3yt":
            if not query:
                self.send_private_message(username, "Usage: !mp3yt <youtube_url>")
                return
            self.handle_ytmp3_command(query)
            return

        # Handle !greeting command
        elif command == "!greeting":
            self.auto_greeting_enabled = not self.auto_greeting_enabled
            state = "enabled" if self.auto_greeting_enabled else "disabled"
            self.send_private_message(username, f"Auto-greeting has been {state}.")
            return

        # Handle !timer command
        elif command == "!timer":
            parts = query.split(maxsplit=1)
            if len(parts) < 2:
                self.send_private_message(username, "Usage: !timer <value> <minutes or seconds>")
                return
            value, unit = parts
            if not value.isdigit() or unit not in ["minutes", "seconds"]:
                self.send_private_message(username, "Invalid timer value or unit. Please use numbers and specify either 'minutes' or 'seconds'.")
                return
            self.handle_timer_command(username, value, unit)
            return

        # Handle !blaz command
        elif command == "!blaz":
            if not query:
                self.send_private_message(username, "Usage: !blaz <WIRL, WKZF, WMBD, WPBG, WSWT, WXCL>")
                return
            call_letters = query.strip().upper()
            radio_links = {
                "WPBG": "https://playerservices.streamtheworld.com/api/livestream-redirect/WPBGFM.mp3",
                "WSWT": "https://playerservices.streamtheworld.com/api/livestream-redirect/WSWTFM.mp3",
                "WMBD": "https://playerservices.streamtheworld.com/api/livestream-redirect/WMBDAM.mp3",
                "WIRL": "https://playerservices.streamtheworld.com/api/livestream-redirect/WIRLAM.mp3",
                "WXCL": "https://playerservices.streamtheworld.com/api/livestream-redirect/WXCLFM.mp3",
                "WKZF": "https://playerservices.streamtheworld.com/api/livestream-redirect/WKZFFM.mp3"
            }
            stream_link = radio_links.get(call_letters, "No matching radio station found.")
            self.send_private_message(username, f"Listen to {call_letters} live: {stream_link}")
            return

        # Handle !radio command
        elif command == "!radio":
            if not query:
                self.send_private_message(username, 'Usage: !radio "search query"')
                return
            match = re.match(r'"([^"]+)"', query)
            if not match:
                self.send_private_message(username, 'Please enclose your search query in quotes, e.g., !radio "classic rock"')
                return
            search_query = match.group(1)
            self.handle_radio_command(search_query)
            return

        # Handle other special commands that need custom processing
        elif command == "!pod":
            parts = message.split(maxsplit=2)
            if len(parts) < 3:
                self.send_private_message(username, "Usage: !pod <show> <episode name or number>")
                return
            show = parts[1]
            episode = parts[2]
            self.handle_pod_command(username, show, episode)
            return
        elif command == "!doc":
            self.handle_doc_command(query, username)
            return
        elif command == "!said":
            self.handle_said_command(username, message)
            return
        elif command == "!mail":
            self.handle_mail_command(message)
            return
        elif command == "!radio":
            match = re.match(r'!radio\s+"([^"]+)"', message)
            if match:
                self.handle_radio_command(match.group(1))
            else:
                self.send_private_message(username, 'Usage: !radio "search query"')
            return

        # Handle standard commands that return responses
        response = None
        if command == "!weather":
            response = self.get_weather_response(query)
        elif command == "!yt":
            response = self.get_youtube_response(query)
        elif command == "!search":
            response = self.get_web_search_response(query)
        elif command == "!chat":
            response = self.get_chatgpt_response(query, username=username)
        elif command == "!news":
            response = self.get_news_response(query)
        elif command == "!map":
            response = self.get_map_response(query)
        elif command == "!pic":
            response = self.get_pic_response(query)
        elif command == "!help":
            # Get all help chunks
            help_chunks = self.get_help_response()
            
            # Send each chunk with a 1-second delay
            def send_delayed_chunk(chunk_index):
                if chunk_index < len(help_chunks):
                    self.send_private_message(username, help_chunks[chunk_index])
                    # Schedule next chunk after 1 second
                    self.master.after(1000, lambda: send_delayed_chunk(chunk_index + 1))
            
            # Start sending chunks
            send_delayed_chunk(0)
            return
        elif command == "!stocks":
            response = self.get_stock_price(query)
        elif command == "!crypto":
            response = self.get_crypto_price(query)
        elif command == "!gif":
            response = self.get_gif_response(query)
        elif command == "!musk":
            response = self.get_musk_post()
        elif command == "!since":
            target = query if query else username
            response = self.handle_since_command(target)
        else:
            # No command matched - treat as chat query
            response = self.get_chatgpt_response(message, username=username)

        # Send response via whisper
        if response:
            self.send_private_message(username, response)

    def handle_page_trigger(self, username, module_or_channel, message):
        """
        Handle page message triggers and respond accordingly.
        """
        response = None  # Initialize response with None
        if "!weather" in message:
            location = message.split("!weather", 1)[1].strip()
            response = self.get_weather_response(location)
        elif "!yt" in message:
            query = message.split("!yt", 1)[1].strip()
            response = self.get_youtube_response(query)
        elif "!search" in message:
            query = message.split("!search", 1)[1].strip()
            response = self.get_web_search_response(query)
        elif "!chat" in message:
            query = message.split("!chat", 1)[1].strip()
            response = self.get_chatgpt_response(query, username=username)
        elif "!news" in message:
            topic = message.split("!news", 1)[1].strip()
            response = self.get_news_response(topic)
        elif "!map" in message:
            place = message.split("!map", 1)[1].strip()
            response = self.get_map_response(place)
        elif "!pic" in message:
            query = message.split("!pic", 1)[1].strip()
            response = self.get_pic_response(query)
        elif "!help" in message:
            help_chunks = self.get_help_response()
            
            def send_delayed_chunk(chunk_index):
                if chunk_index < len(help_chunks):
                    self.send_page_response(username, module_or_channel, help_chunks[chunk_index])
                    # Schedule next chunk after 1 second
                    self.master.after(1000, lambda: send_delayed_chunk(chunk_index + 1))
            
            # Start sending chunks
            send_delayed_chunk(0)
            return
        elif "!stocks" in message:
            symbol = message.split("!stocks", 1)[1].strip()
            response = self.get_stock_price(symbol)
        elif "!crypto" in message:
            crypto = message.split("!crypto", 1)[1].strip()
            response = self.get_crypto_price(crypto)
        elif "!who" in message:
            response = self.get_who_response()
        elif "!seen" in message:
            target_username = message.split("!seen", 1)[1].strip()
            response = self.get_seen_response(target_username)
        elif "!gif" in message:
            query = message.split("!gif", 1)[1].strip()
            response = self.get_gif_response(query)
        elif "!doc" in message:
            query = message.split("!doc", 1)[1].strip()
            self.handle_doc_command(query, username)
        elif "!said" in message:
            self.handle_said_command(username, message, is_page=True, module_or_channel=module_or_channel)
        elif "!pod" in message:
            parts = message.split(maxsplit=2)
            if len(parts) < 3:
                self.send_page_response(username, module_or_channel, "Usage: !pod <show> <episode name or number>")
                return
            show = parts[1]
            episode = parts[2]
            self.handle_pod_command(username, show, episode, is_page=True, module_or_channel=module_or_channel)
            return
        elif "!mail" in message:
            self.handle_mail_command(message)
        elif "!radio" in message:
            match = re.match(r'!radio\s+"([^"]+)"', message)
            if match:
                query = match.group(1)
                self.handle_radio_command(query)
            else:
                self.send_page_response(username, module_or_channel, 'Usage: !radio "search query"')
        elif "!musk" in message:
            response = self.get_musk_post()
        elif "!since" in message:
            parts = message.split("!since", 1)[1].strip()
            response = self.handle_since_command(parts if parts else username)

        if response:
            self.send_page_response(username, module_or_channel, response)

    

    

    def handle_direct_message(self, username, message):
        """
        Handle direct messages and interpret them as !chat queries.
        """
        self.refresh_membership()  # Refresh membership before generating response
        time.sleep(1)  # Allow time for membership list to be updated
        self.master.update()  # Process any pending updates

        # Fetch the latest chat members from DynamoDB
        self.chat_members = set(self.get_chat_members())
        print(f"[DEBUG] Updated chat members list before generating response: {self.chat_members}")

        if "who's here" in message.lower() or "who is here" in message.lower():
            query = "who else is in the chat room?"
            response = self.get_chatgpt_response(query, direct=True, username=username)
        elif "!said" in message:
            self.handle_said_command(username, message)
            return
        elif "!pod" in message:
            parts = message.split(maxsplit=2)
            if len(parts) < 3:
                self.send_direct_message(username, "Usage: !pod <show> <episode name or number>")
                return
            show = parts[1]
            episode = parts[2]
            self.handle_pod_command(username, show, episode)
            return
        elif "!mail" in message:
            self.handle_mail_command(message)
            return
        elif "!radio" in message:
            match = re.match(r'!radio\s+"([^"]+)"', message)
            if match:
                query = match.group(1)
                self.handle_radio_command(query)
            else:
                self.send_direct_message(username, 'Usage: !radio "search query"')
                return
        elif "!musk" in message:
            response = self.get_musk_post()
        elif "!since" in message:
            target = message.split("!since", 1)[1].strip()
            response = self.handle_since_command(target if target else username)
        else:
            response = self.get_chatgpt_response(message, direct=True, username=username)

        self.send_direct_message(username, response)

    def send_direct_message(self, username, message):
        """
        Send a direct message to the specified user.
        """
        chunks = self.chunk_message(message, 250)
        for i, chunk in enumerate(chunks):
            full_message = f">{username} {chunk}"
            asyncio.run_coroutine_threadsafe(self._send_message(full_message + "\r\n"), self.loop)
            self.append_terminal_text(full_message + "\n", "normal")
            if i < len(chunks) - 1:
                time.sleep(0.5)  # Add 0.5 second delay between chunks

    def get_weather_response(self, args):
        """Fetch weather info and return a ChatGPT-generated response as a string."""
        key = self.weather_api_key.get()
        if not key:
            return "Weather API key is missing."

        # Split args into command, city, and state 
        parts = args.strip().split(maxsplit=3)
        if len(parts) < 3:
            return "Usage: !weather <current/forecast> <city> <state>"

        command, city, state = parts[0], parts[1], parts[2]
        if command.lower() not in ['current', 'forecast']:
            return "Please specify either 'current' or 'forecast' as the first argument."

        if not city or not state:
            return "Please specify both city and state."

        location = f"{city},{state}"

        try:
            if command.lower() == 'current':
                url = "http://api.openweathermap.org/data/2.5/weather"
                params = {
                    "q": location,
                    "appid": key,
                    "units": "imperial"
                }
                r = requests.get(url, params=params, timeout=10)
                r.raise_for_status()
                data = r.json()
                
                if data.get("cod") != 200:
                    return f"Could not get weather for '{location}'."

                # Prepare weather info dictionary
                weather_info = {
                    "location": f"{city.title()}, {state.upper()}",
                    "description": data["weather"][0]["description"],
                    "temp_f": data["main"]["temp"],
                    "feels_like": data["main"]["feels_like"],
                    "humidity": data["main"]["humidity"],
                    "wind_speed": data["wind"]["speed"],
                    "precipitation": data.get("rain", {}).get("1h", 0) + data.get("snow", {}).get("1h", 0)
                }

                # Create a concise single-line response
                response = (
                    f"Weather in {weather_info['location']}: {weather_info['description']}, "
                    f"{weather_info['temp_f']:.1f}°F (feels like {weather_info['feels_like']:.1f}°F), "
                    f"humidity {weather_info['humidity']}%, wind {weather_info['wind_speed']} mph"
                )

            else:  # forecast
                url = "http://api.openweathermap.org/data/2.5/forecast"
                params = {
                    "q": location,
                    "appid": key,
                    "units": "imperial"
                }
                r = requests.get(url, params=params, timeout=10)
                r.raise_for_status()
                data = r.json()
                
                if data.get("cod") != "200":
                    return f"Could not get forecast for '{location}'."

                # Create a concise 3-day forecast
                forecasts = []
                current_date = None
                for item in data['list']:
                    date = time.strftime('%Y-%m-%d', time.localtime(item['dt']))
                    if date == time.strftime('%Y-%m-%d'):  # Skip today
                        continue
                    if date != current_date and len(forecasts) < 3:
                        current_date = date
                        temp = item['main']['temp']
                        desc = item['weather'][0]['description']
                        day = time.strftime('%A', time.localtime(item['dt']))
                        forecasts.append(f"{day}: {desc}, {temp:.1f}°F")

                response = f"3-day forecast for {city.title()}, {state.upper()}: " + " | ".join(forecasts)

            return response

        except requests.exceptions.RequestException as e:
            return f"Error fetching weather: {str(e)}"

    def get_youtube_response(self, query):
        """Perform a YouTube search and return the response as a string."""
        key = self.youtube_api_key.get()
        if not key:
            return "YouTube API key is missing."
        else:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "key": key,
                "maxResults": 1
            }
            try:
                r = requests.get(url, params=params)
                data = r.json()
                items = data.get("items", [])
                if not items:
                    return f"No YouTube results found for '{query}'."
                else:
                    video_id = items[0]["id"].get("videoId")
                    title = items[0]["snippet"]["title"]
                    url_link = f"https://www.youtube.com/watch?v={video_id}"
                    return f"Top YouTube result: {title}\n{url_link}"
            except Exception as e:
                return f"Error fetching YouTube results: {str(e)}"

    def get_web_search_response(self, query):
        """Perform a Google Custom Search and return the response as a string."""
        cse_key = self.google_cse_api_key.get()
        cse_id = self.google_cse_cx.get()
        if not cse_key or not cse_id:
            return "Google CSE API key or engine ID is missing."
        else:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": cse_key,
                "cx": cse_id,
                "q": query,
                "num": 1  # just one top result
            }
            try:
                r = requests.get(url, params=params)
                data = r.json()
                items = data.get("items", [])
                if not items:
                    return f"No Google search results found for '{query}'."
                else:
                    top = items[0]
                    title = top.get("title", "No Title")
                    snippet = top.get("snippet", "")
                    link = top.get("link", "No Link")

                    return (
                        f"Top Google result for '{query}':\n"
                        f"Title: {title}\n"
                        f"Snippet: {snippet}\n"
                        f"Link: {link}"
                    )
            except Exception as e:
                return f"Error with Google search: {str(e)}"

    def get_chatgpt_response(self, user_text, direct=False, username=None):
        """Send user_text to ChatGPT and return the response as a string."""
        if not self.openai_client:
            return "OpenAI client is not initialized."

        # Fetch the latest chat members from DynamoDB
        self.chat_members = set(self.get_chat_members())
        members = list(self.chat_members)
        print(f"[DEBUG] Members list used for ChatGPT response: {members}")

        # Turn user@domain into just the username portion if you want:
        chatroom_usernames = []
        for member in members:
            name_part = member.split('@')[0]
            chatroom_usernames.append(name_part)

        # Create a simple comma-separated string for the system prompt
        chatroom_members_str = ", ".join(chatroom_usernames)
        print(f"[DEBUG] Chatroom members string for ChatGPT: {chatroom_members_str}")

        system_message = (
            "Your name is Ultron. You speak very casually. When you greet people, you usually say things like 'Hey :)', 'What's up?', 'How's it going?'. "
            "You are just a laidback guy, hanging out in the bbs chatroom. "
            "Respond concisely in 220-characters or less but don't exceed 250 total characters in your responses. "
            "If asked about who's in the room, reference the current chatroom members list. "
            "You are speaking in a BBS plain text chatroom, please make sure any emoji you use are plain text, and that the format of your responses is ideal for plain text. "
            f"The current chatroom members are: {chatroom_members_str}."
        )

        if direct:
            system_message = (
                "Your name is Ultron. You speak very casually. When you greet people, you usually say things like 'Hey :)', 'What's up?', 'How's it going?'. "
                "You are just a laidback guy, hanging out in the bbs chatroom. "
                "Respond concisely in 220-characters or less but don't exceed 250 total characters in your responses. "
                "If asked about who's in the room, reference the current chatroom members list. "
                "You are speaking in a BBS plain text chatroom, please make sure any emoji you use are plain text, and that the format of your responses is ideal for plain text. "
                f"The current chatroom members are: {chatroom_members_str}."
            )

        # Optionally load conversation history from DynamoDB
        if username:
            conversation_history = self.get_conversation_history(username)
        else:
            conversation_history = self.get_conversation_history("public_chat")

        # Truncate conversation history to the last 5 messages
        truncated_history = conversation_history[-5:]

        messages = [
            {"role": "system", "content": system_message}
        ]
        # Then append user messages and assistant replies from the truncated history
        for item in truncated_history:
            messages.append({"role": "user", "content": item['message']})
            messages.append({"role": "assistant", "content": item['response']})

        # (Optional) add a mini fact about who is speaking:
        if username:
            messages.append({"role": "system", "content": f"Reminder: The user speaking is named {username}."})

        # Finally append this new user_text
        messages.append({"role": "user", "content": user_text})

        print(f"[DEBUG] Chunks sent to ChatGPT: {messages}")  # Log chunks sent to ChatGPT

        try:
            completion = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                n=1,
                max_tokens=500,  # Allow for longer responses
                temperature=0.2,  # Set temperature to 0.2
                messages=messages
            )
            gpt_response = completion.choices[0].message.content

            if username:
                self.save_conversation(username, user_text, gpt_response)
            else:
                self.save_conversation("public_chat", user_text, gpt_response)

        except Exception as e:
            gpt_response = f"Error with ChatGPT API: {str(e)}"

        print(f"[DEBUG] ChatGPT response: {gpt_response}")  # Log ChatGPT response
        return gpt_response

    def get_map_response(self, place):
        """Fetch place info from Google Places API and return the response as a string."""
        key = self.google_places_api_key.get()
        if not key:
            return "Google Places API key is missing."
        elif not place:
            return "Please specify a place."
        else:
            url = "https://places.googleapis.com/v1/places:searchText"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.types,places.websiteUri"
            }
            data = {
                "textQuery": place
            }
            try:
                r = requests.post(url, json=data, headers=headers, timeout=10)
                r.raise_for_status()  # Raise an HTTPError for bad responses
                data = r.json()
                places = data.get("places", [])
                if not places:
                    return f"Could not find place '{place}'."
                else:
                    place_info = places[0]
                    name = place_info.get("displayName", {}).get("text", "No Name")
                    address = place_info.get("formattedAddress", "No Address")
                    types = ", ".join(place_info.get("types", []))
                    website = place_info.get("websiteUri", "No Website")
                    return (
                        f"Place: {name}\n"
                        f"Address: {address}\n"
                        f"Types: {types}\n"
                        f"Website: {website}"
                    )
            except requests.exceptions.RequestException as e:
                return f"Error fetching place info: {str(e)}"

    def get_help_response(self):
        """Return the help message as chunks that fit within BBS line limits."""
        commands = [
            "Use '!' followed by a keyword(no space)", "weather <location>", "yt <query>", "search <query>", 
            "chat <message>", "news <topic>", "map <place>", 
            "pic <img/gif> <query>", "polly <voice> <text>", 
            "mp3yt <youtube_url>", "help", "seen <username>", "greeting",
            "stocks <symbol>", "crypto <symbol>", 
            "timer <value> <minutes/seconds>", "gif <query>", 
            "msg <username> <message>", "doc <topic>", "pod <show> <episode>",
            "trump", "nospam", "blaz <call_letters>", "radio <query>",
            "musk", "since <username>", "said <username>",
            "mail <recipient> <subject> <body>"
        ]
        
        chunks = []
        current_chunk = "Available commands: "
        char_limit = 180  # Reduced from 230 to ensure safer delivery
        
        for cmd in commands:
            # Check if adding this command would exceed the limit
            if len(current_chunk) + len(cmd) + 2 <= char_limit:
                current_chunk += cmd + ", "
            else:
                # Remove trailing comma and space before adding to chunks
                chunks.append(current_chunk.rstrip(", "))
                # Start new chunk with the command that wouldn't fit
                current_chunk = cmd + ", "
        
        # Add the final chunk if there's anything left
        if current_chunk:
            chunks.append(current_chunk.rstrip(", "))
        
        # Add chunk numbers for clarity
        final_chunks = []
        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                final_chunks.append(f"{chunk} ({i}/{len(chunks)})")
            else:
                final_chunks.append(chunk)
        
        return final_chunks

    def append_terminal_text(self, text, default_tag="normal"):
        """Append text to the terminal display with ANSI parsing."""
        self.terminal_display.configure(state=tk.NORMAL)
        self.parse_ansi_and_insert(text)
        self.terminal_display.see(tk.END)
        self.terminal_display.configure(state=tk.DISABLED)

    def parse_ansi_and_insert(self, text_data):
        """Minimal parser for ANSI color codes (foreground only)."""
        ansi_escape_regex = re.compile(r'\x1b\[(.*?)m')

        last_end = 0
        current_tag = "normal"

        for match in ansi_escape_regex.finditer(text_data):
            start, end = match.span()
            # Insert text before this ANSI code with current tag
            if start > last_end:
                self.terminal_display.insert(tk.END, text_data[last_end:start].replace('& # 3 9 ;', "'"), current_tag)

            code_string = match.group(1)
            codes = code_string.split(';')
            if '0' in codes:
                current_tag = "normal"
                codes.remove('0')

            for c in codes:
                mapped_tag = self.map_code_to_tag(c)
                if mapped_tag:
                    current_tag = mapped_tag

            last_end = end

        if last_end < len(text_data):
            self.terminal_display.insert(tk.END, text_data[last_end:].replace('& # 3 9 ;', "'"), current_tag)

    def map_code_to_tag(self, color_code):
        """Map a numeric color code to a defined Tk text tag."""
        valid_codes = {
            '30': 'black',
            '31': 'red',
            '32': 'green',
            '33': 'yellow',
            '34': 'blue',
            '35': 'magenta',
            '36': 'cyan',
            '37': 'white',
            '90': 'bright_black',
            '91': 'bright_red',
            '92': 'bright_green',
            '93': 'bright_yellow',
            '94': 'bright_blue',
            '95': 'bright_magenta',
            '96': 'bright_cyan',
            '97': 'bright_white',
        }
        return valid_codes.get(color_code, None)

    def replace_newline_markers(self, text):
        """Replace /n markers with actual newline characters."""
        return text.replace("/n", "\n")

    def send_message(self, event=None):
        """Send the user's typed message to the BBS."""
        if not self.connected or not self.writer:
            self.append_terminal_text("Not connected to any BBS.\n", "normal")
            return

        user_input = self.input_var.get()
        self.input_var.set("")
        # Replace the /n markers with newline characters
        processed_input = self.replace_newline_markers(user_input)

        if processed_input.strip():
            prefix = "Gos " if self.mud_mode.get() else ""
            message = prefix + processed_input
            asyncio.run_coroutine_threadsafe(self._send_message(message + "\r\n"), self.loop)
            self.append_terminal_text(message + "\n", "normal")
            print(f"Sent to BBS: {message}")

    async def _send_message(self, message):
        """Coroutine to send a message with error handling."""
        try:
            if self.writer:
                self.writer.write(message)
                await asyncio.wait_for(self.writer.drain(), timeout=3.0)
        except asyncio.TimeoutError:
            print(f"Timeout sending message: {message}")
            # Optionally retry or handle the timeout
        except Exception as e:
            print(f"Error sending message: {str(e)}")

    def send_full_message(self, message):
        """
        Send a full message to the terminal display and the BBS server.
        """
        if message is None:
            return  # Avoid sending if the message is None

        prefix = "Gos " if self.mud_mode.get() else ""
        lines = message.split('\n')
        full_message = '\n'.join([prefix + line for line in lines])
        chunks = self.chunk_message(full_message, 250)  # Use the new chunk_message!

        for chunk in chunks:
            self.append_terminal_text(chunk + "\n", "normal")
            if self.connected and self.writer:
                asyncio.run_coroutine_threadsafe(self._send_message(chunk + "\r\n"), self.loop)
                time.sleep(0.1)  # Add a short delay to ensure messages are sent in sequence
                print(f"Sent to BBS: {chunk}")  # Log chunks sent to BBS

    def chunk_message(self, message, chunk_size):
        """
        Break a message into chunks, up to `chunk_size` characters each,
        ensuring no splits in the middle of words or lines.

        1. Split by newline to preserve paragraph boundaries.
        2. For each paragraph, break it into word-based lines
           that do not exceed chunk_size.
        """
        paragraphs = message.split('\n')
        final_chunks = []

        for para in paragraphs:
            # If paragraph is totally empty, keep it as a blank line
            if not para.strip():
                final_chunks.append('')
                continue

            words = para.split()
            current_line_words = []

            for word in words:
                if not current_line_words:
                    # Start a fresh line
                    current_line_words.append(word)
                else:
                    # Test if we can add " word" without exceeding chunk_size
                    test_line = ' '.join(current_line_words + [word])
                    if len(test_line) <= chunk_size:
                        current_line_words.append(word)
                    else:
                        # We have to finalize the current line
                        final_chunks.append(' '.join(current_line_words))
                        current_line_words = [word]

            # Any leftover words in current_line_words
            if current_line_words:
                final_chunks.append(' '.join(current_line_words))

        return final_chunks

    def show_favorites_window(self):
        """Open a Toplevel window to manage favorite BBS addresses."""
        if self.favorites_window and self.favorites_window.winfo_exists():
            self.favorites_window.lift()
            return

        self.favorites_window = tk.Toplevel(self.master)
        self.favorites_window.title("Favorite BBS Addresses")

        row_index = 0

        # Listbox to display favorite addresses
        self.favorites_listbox = tk.Listbox(self.favorites_window, height=10, width=50)
        self.favorites_listbox.grid(row=row_index, column=0, columnspan=2, padx=5, pady=5)
        self.update_favorites_listbox()

        row_index += 1

        # Entry to add a new favorite address
        self.new_favorite_var = tk.StringVar()
        ttk.Entry(self.favorites_window, textvariable=self.new_favorite_var, width=40).grid(row=row_index, column=0, padx=5, pady=5)

        # Button to add the new favorite address
        add_button = ttk.Button(self.favorites_window, text="Add", command=self.add_favorite)
        add_button.grid(row=row_index, column=1, padx=5, pady=5)

        row_index += 1

        # Button to remove the selected favorite address
        remove_button = ttk.Button(self.favorites_window, text="Remove", command=self.remove_favorite)
        remove_button.grid(row=row_index, column=0, columnspan=2, pady=5)

        # Bind listbox selection to populate host field
        self.favorites_listbox.bind("<<ListboxSelect>>", self.populate_host_field)

    def update_favorites_listbox(self):
        """Update the Listbox with the current favorite addresses."""
        self.favorites_listbox.delete(0, tk.END)
        for address in self.favorites:
            self.favorites_listbox.insert(tk.END, address)

    def add_favorite(self):
        """Add a new favorite address."""
        new_address = self.new_favorite_var.get().strip()
        if new_address and new_address not in self.favorites:
            self.favorites.append(new_address)
            self.update_favorites_listbox()
            self.new_favorite_var.set("")
            self.save_favorites()

    def remove_favorite(self):
        """Remove the selected favorite address."""
        selected_index = self.favorites_listbox.curselection()
        if selected_index:
            address = self.favorites_listbox.get(selected_index)
            self.favorites.remove(address)
            self.update_favorites_listbox()
            self.save_favorites()

    def load_favorites(self):
        """Load favorite BBS addresses from a file."""
        if os.path.exists("favorites.json"):
            with open("favorites.json", "r") as file:
                return json.load(file)
        return []

    def save_favorites(self):
        """Save favorite BBS addresses to a file."""
        with open("favorites.json", "w") as file:
            json.dump(self.favorites, file)

    def populate_host_field(self, event):
        """Populate the host field with the selected favorite address."""
        selected_index = self.favorites_listbox.curselection()
        if selected_index:
            address = self.favorites_listbox.get(selected_index)
            self.host.set(address)

    def load_nickname(self):
        """Load nickname from a file."""
        if os.path.exists("nickname.json"):
            with open("nickname.json", "r") as file:
                return json.load(file)
        return ""

    def save_nickname(self):
        """Save nickname to a file."""
        with open("nickname.json", "w") as file:
            json.dump(self.nickname.get(), file)

    def send_username(self):
        """Send the username to the BBS."""
        if self.connected and self.writer:
            username = self.username.get()
            asyncio.run_coroutine_threadsafe(self._send_message(username + "\r\n"), self.loop)  # Append carriage return and newline
            if self.remember_username.get():
                self.save_username()

    def send_password(self):
        """Send the password to the BBS."""
        if self.connected and self.writer:
            password = self.password.get()
            asyncio.run_coroutine_threadsafe(self._send_message(password + "\r\n"), self.loop)  # Append carriage return and newline
            if self.remember_password.get():
                self.save_password()

    def load_username(self):
        """Load username from a file."""
        if os.path.exists("username.json"):
            with open("username.json", "r") as file:
                return json.load(file)
        return ""

    def save_username(self):
        """Save username to a file."""
        with open("username.json", "w") as file:
            json.dump(self.username.get(), file)

    def load_password(self):
        """Load password from a file."""
        if os.path.exists("password.json"):
            with open("password.json", "r") as file:
                return json.load(file)
        return ""

    def save_password(self):
        """Save password to a file."""
        with open("password.json", "w") as file:
            json.dump(self.password.get(), file)

    ########################################################################
    #                           Trigger Parsing
    ########################################################################
    def parse_incoming_triggers(self, line):
        # Remove ANSI codes for easier parsing.
        ansi_escape_regex = re.compile(r'\x1b\[(.*?)m')
        clean_line = ansi_escape_regex.sub('', line)

        # Always allow the !nospam command to toggle state
        if "!nospam" in clean_line:
            # Toggle and persist the new state
            self.no_spam_mode.set(not self.no_spam_mode.get())
            state = "enabled" if self.no_spam_mode.get() else "disabled"
            self.send_full_message(f"No Spam Mode has been {state}.")
            self.save_no_spam_state()
            return

        # Detect message types
        private_message_match = re.match(r'From (.+?) \(whispered\): (.+)', clean_line)
        page_message_match = re.match(r'(.+?) is paging you from (.+?): (.+)', clean_line)
        direct_message_match = re.match(r'From (.+?) \(to you\): (.+)', clean_line)

        # If !nospam is ON, only allow whispered and paging messages.
        if self.no_spam_mode.get() and not (private_message_match or page_message_match):
            self.append_terminal_text("Ignored trigger due to No Spam Mode.\n", "normal")
            return

        # Process private messages
        if private_message_match:
            username = private_message_match.group(1)
            message = private_message_match.group(2)
            self.handle_private_trigger(username, message)
        else:
            # Process page commands
            if page_message_match:
                username = page_message_match.group(1)
                module_or_channel = page_message_match.group(2)
                message = page_message_match.group(3)
                self.handle_page_trigger(username, module_or_channel, message)
            # Process direct messages (only if !nospam is OFF)
            elif direct_message_match:
                username = direct_message_match.group(1)
                message = direct_message_match.group(2)
                self.handle_direct_message(username, message)
            else:
                # Process known commands.
                public_trigger_match = re.match(r'From (.+?): (.+)', clean_line)
                if public_trigger_match:
                    sender = public_trigger_match.group(1)
                    message = public_trigger_match.group(2)

                    # Always store the public message.
                    self.store_public_message(sender, message)

                    # Ignore messages from Ultron (the bot itself).
                    if sender.lower() == "ultron":
                        return

                    # Only process messages that begin with a recognized command.
                    valid_commands = [
                        "!weather", "!yt", "!search", "!chat", "!news", "!map",
                        "!pic", "!polly", "!mp3yt", "!help", "!seen", "!greeting",
                        "!stocks", "!crypto", "!timer", "!gif", "!msg", "!doc", "!pod", "!said", "!trump", "!mail", "!blaz", "!musk", "!since"
                    ]
                    if not any(message.startswith(cmd) for cmd in valid_commands):
                        return

                    # Process recognized commands.
                    if message.startswith("!weather"):
                        location = message.split("!weather", 1)[1].strip()
                        self.send_full_message(self.get_weather_response(location))
                    elif message.startswith("!yt"):
                        query = message.split("!yt", 1)[1].strip()
                        self.send_full_message(self.get_youtube_response(query))
                    elif message.startswith("!search"):
                        query = message.split("!search", 1)[1].strip()
                        self.send_full_message(self.get_web_search_response(query))
                    elif message.startswith("!chat"):
                        query = message.split("!chat", 1)[1].strip()
                        self.send_full_message(self.get_chatgpt_response(query, username=sender))
                    elif message.startswith("!news"):
                        topic = message.split("!news", 1)[1].strip()
                        self.send_full_message(self.get_news_response(topic))
                    elif message.startswith("!map"):
                        place = message.split("!map", 1)[1].strip()
                        self.send_full_message(self.get_map_response(place))
                    elif message.startswith("!pic"):
                        query = message.split("!pic", 1)[1].strip()
                        self.send_full_message(self.get_pic_response(query))
                    elif message.startswith("!polly"):
                        parts = message.split(maxsplit=2)
                        if len(parts) < 3:
                            self.send_full_message("Usage: !polly <voice> <text> - Voices are Ruth, Joanna, Danielle, Matthew, Stephen")
                        else:
                            voice = parts[1]
                            text = parts[2]
                            self.handle_polly_command(voice, text)
                    elif message.startswith("!mp3yt"):
                        url = message.split("!mp3yt", 1)[1].strip()
                        self.handle_ytmp3_command(url)
                    elif message.startswith("!help"):
                        self.handle_help_command()
                    elif message.startswith("!seen"):
                        target_username = message.split("!seen", 1)[1].strip()
                        self.send_full_message(self.get_seen_response(target_username))
                    elif message.startswith("!greeting"):
                        self.handle_greeting_command()
                    elif message.startswith("!stocks"):
                        symbol = message.split("!stocks", 1)[1].strip()
                        self.send_full_message(self.get_stock_price(symbol))
                    elif message.startswith("!crypto"):
                        crypto = message.split("!crypto", 1)[1].strip()
                        self.send_full_message(self.get_crypto_price(crypto))
                    elif message.startswith("!timer"):
                        parts = message.split(maxsplit=3)
                        if len(parts) < 3:
                            self.send_full_message("Usage: !timer <value> <minutes or seconds>")
                        else:
                            value = parts[1]
                            unit = parts[2]
                            self.handle_timer_command(sender, value, unit)
                    elif message.startswith("!gif"):
                        query = message.split("!gif", 1)[1].strip()
                        self.send_full_message(self.get_gif_response(query))
                    elif message.startswith("!msg"):
                        parts = message.split(maxsplit=2)
                        if len(parts) < 3:
                            self.send_full_message("Usage: !msg <username> <message>")
                        else:
                            recipient = parts[1]
                            message = parts[2]
                            self.handle_msg_command(recipient, message, sender)
                    elif message.startswith("!doc"):
                        query = message.split("!doc", 1)[1].strip()
                        self.handle_doc_command(query, sender, public=True)
                    elif message.startswith("!pod"):
                        self.handle_pod_command(sender, message)
                    elif message.startswith("!said"):
                        self.handle_said_command(sender, message)
                        return
                    elif message.startswith("!trump"):
                        trump_text = self.get_trump_post()
                        chunks = self.chunk_message(trump_text, 250)
                        for chunk in chunks:
                            self.send_full_message(chunk)
                        return
                    elif message.startswith("!mail"):
                        self.handle_mail_command(message)
                    elif message.startswith("!blaz"):
                        call_letters = message.split("!blaz", 1)[1].strip()
                        self.handle_blaz_command(call_letters)
                    elif message.startswith("!musk"):
                        response = self.get_musk_post()
                        self.send_full_message(response)
                    elif message.startswith("!since"):
                        parts = message.split("!since", 1)[1].strip()
                        response = self.handle_since_command(parts if parts else sender)
                        if response:
                            if self.no_spam_mode.get() or self.no_spam_perm:
                                self.send_private_message(sender, response)
                            else:
                                self.send_full_message(response)

        # Update the previous line
        self.previous_line = clean_line

    


    def get_who_response(self):
        """Return a list of users currently in the chatroom."""
        if not self.chat_members:
            return "No users currently in the chatroom."
        else:
            return "Users currently in the chatroom: " + ", ".join(self.chat_members)

    def send_page_response(self, username, module_or_channel, message):
        """
        Send a page response to the specified user and module/channel.
        """
        chunks = self.chunk_message(message, 250)
        for chunk in chunks:
            full_message = f"/P {username} {chunk}"
            asyncio.run_coroutine_threadsafe(self._send_message(full_message + "\r\n"), self.loop)
            self.append_terminal_text(full_message + "\n", "normal")

    ########################################################################
    #                           Help
    ########################################################################
    def handle_help_command(self):
        """Provide a list of available commands, adhering to character and chunk limits."""
        help_chunks = self.get_help_response()
        
        # Join the help chunks into a single string
        help_message = "\n".join(help_chunks)
        
        # Send the help message
        self.send_full_message(help_message)

    ########################################################################
    #                           Weather
    ########################################################################
    def handle_weather_command(self, location):
        """Fetch weather info and relay it to the user using ChatGPT."""
        key = self.weather_api_key.get()
        if not key:
            response = "Weather API key is missing."
        elif not location:
            response = "Please specify a city or zip code."
        else:
            url = "http://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": location,
                "appid": key,
                "units": "imperial"
            }
            try:
                r = requests.get(url, params=params, timeout=10)
                r.raise_for_status()  # Raise an HTTPError for bad responses
                data = r.json()
                if data.get("cod") != 200:
                    response = f"Could not get weather for '{location}'."
                else:
                    weather_info = {
                        "location": location.title(),
                        "description": data["weather"][0]["description"],
                        "temp_f": data["main"]["temp"],
                        "feels_like": data["main"]["feels_like"],
                        "humidity": data["main"]["humidity"],
                        "wind_speed": data["wind"]["speed"],
                        "precipitation": data.get("rain", {}).get("1h", 0) + data.get("snow", {}).get("1h", 0)
                    }

                    # Prepare the prompt for ChatGPT
                    prompt = (
                        f"The weather in {weather_info['location']} is currently described as {weather_info['description']}. "
                        f"The temperature is {weather_info['temp_f']:.1f}°F, but it feels like {weather_info['feels_like']:.1f}°F. "
                        f"The humidity is {weather_info['humidity']}%, and the wind speed is {weather_info['wind_speed']} mph. "
                        f"There is {weather_info['precipitation']} mm of precipitation. "
                        "Please relay this weather information to the user in a friendly and natural way."
                    )

                    # Get the response from ChatGPT
                    chatgpt_response = self.get_chatgpt_response(prompt)
                    response = chatgpt_response
            except requests.exceptions.RequestException as e:
                response = f"Error fetching weather: {str(e)}"

        self.send_full_message(response)

    ########################################################################
    #                           YouTube
    ########################################################################
    def handle_youtube_command(self, query):
        """Perform a YouTube search for the given query (unlimited length)."""
        key = self.youtube_api_key.get()
        if not key:
            response = "YouTube API key is missing."
        else:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "key": key,
                "maxResults": 1
            }
            try:
                r = requests.get(url, params=params)
                data = r.json()
                items = data.get("items", [])
                if not items:
                    response = f"No YouTube results found for '{query}'."
                else:
                    video_id = items[0]["id"].get("videoId")
                    title = items[0]["snippet"]["title"]
                    url_link = f"https://www.youtube.com/watch?v={video_id}"
                    response = f"Top YouTube result: {title}\n{url_link}"
            except Exception as e:
                response = f"Error fetching YouTube results: {str(e)}"

        self.send_full_message(response)

    ########################################################################
    #                           Google Custom Search (with Link)
    ########################################################################
    def handle_web_search_command(self, query):
        """
        Perform a Google Custom Search (unlimited length) for better link display.
        """
        cse_key = self.google_cse_api_key.get()
        cse_id = self.google_cse_cx.get()
        if not cse_key or not cse_id:
            response = "Google CSE API key or engine ID is missing."
        else:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": cse_key,
                "cx": cse_id,
                "q": query,
                "num": 1  # just one top result
            }
            try:
                r = requests.get(url, params=params)
                data = r.json()
                items = data.get("items", [])
                if not items:
                    response = f"No Google search results found for '{query}'."
                else:
                    top = items[0]
                    title = top.get("title", "No Title")
                    snippet = top.get("snippet", "")
                    link = top.get("link", "No Link")

                    response = (
                        f"Top Google result for '{query}':\n"
                        f"Title: {title}\n"
                        f"Snippet: {snippet}\n"
                        f"Link: {link}"
                    )
            except Exception as e:
                response = f"Error with Google search: {str(e)}"

        self.send_full_message(response)

    ########################################################################
    #                           ChatGPT
    ########################################################################
    def handle_chatgpt_command(self, user_text, username=None):
        """
        Send user_text to ChatGPT and handle responses.
        The response can be longer than 220 characters but will be split into blocks.
        """
        self.refresh_membership()  # Refresh membership before generating response
        time.sleep(1)  # Allow time for membership list to be updated
        self.master.update()  # Process any pending updates

        # Fetch the latest chat members from DynamoDB
        self.chat_members = set(self.get_chat_members())
        print(f"[DEBUG] Updated chat members list before generating response: {self.chat_members}")

        response = self.get_chatgpt_response(user_text, username=username)
        self.send_full_message(response)

        # Save the conversation for non-directed messages
        if username is None:
            username = "public_chat"
        self.save_conversation(username, user_text, response)

    ########################################################################
    #                           News
    ########################################################################
    def handle_news_command(self, topic):
        """Fetch top 2 news headlines based on the given topic."""
        response = self.get_news_response(topic)
        chunks = self.chunk_message(response, 250)
        for chunk in chunks:
            self.send_full_message(chunk)

    ########################################################################
    #                           Map
    ########################################################################
    def handle_map_command(self, place):
        """Fetch place info from Google Places API and return the response as a string."""
        key = self.google_places_api_key.get()
        if not key:
            response = "Google Places API key is missing."
        elif not place:
            response = "Please specify a place."
        else:
            url = "https://places.googleapis.com/v1/places:searchText"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.types,places.websiteUri"
            }
            data = {
                "textQuery": place
            }
            try:
                r = requests.post(url, json=data, headers=headers, timeout=10)
                r.raise_for_status()  # Raise an HTTPError for bad responses
                data = r.json()
                places = data.get("places", [])
                if not places:
                    response = f"Could not find place '{place}'."
                else:
                    place_info = places[0]
                    name = place_info.get("displayName", {}).get("text", "No Name")
                    address = place_info.get("formattedAddress", "No Address")
                    types = ", ".join(place_info.get("types", []))
                    website = place_info.get("websiteUri", "No Website")
                    response = (
                        f"Place: {name}\n"
                        f"Address: {address}\n"
                        f"Types: {types}\n"
                        f"Website: {website}"
                    )
            except requests.exceptions.RequestException as e:
                response = f"Error fetching place info: {str(e)}"

        self.send_full_message(response)

    ########################################################################
    #                           Keep Alive
    ########################################################################
    async def keep_alive(self):
        """Send an <ENTER> keystroke every 10 seconds to keep the connection alive."""
        while not self.keep_alive_stop_event.is_set():
            if self.connected and self.writer:
                self.writer.write("\r\n")
                await self.writer.drain()
            await asyncio.sleep(10)

    def start_keep_alive(self):
        """Start the keep-alive coroutine."""
        self.keep_alive_stop_event.clear()
        if self.loop:
            self.keep_alive_task = self.loop.create_task(self.keep_alive())

    def stop_keep_alive(self):
        """Stop the keep-alive coroutine."""
        self.keep_alive_stop_event.set()
        if self.keep_alive_task:
            self.keep_alive_task.cancel()

    def handle_user_greeting(self, username):
        """
        Handle user-specific greeting when they enter the chatroom.
        """
        if not self.auto_greeting_enabled:
            return

        self.send_enter_keystroke()  # Send ENTER keystroke to get the list of users
        time.sleep(1)  # Wait for the response to be processed
        current_members = self.chat_members.copy()
        new_member_username = username.split('@')[0]  # Remove the @<bbsaddress> part
        if new_member_username not in current_members:
            greeting_message = f"{new_member_username} just came into the chatroom, give them a casual greeting directed at them."
            response = self.get_chatgpt_response(greeting_message, direct=True, username=new_member_username)
            self.send_direct_message(new_member_username, response)

    def handle_pic_command(self, query):
        """Fetch a random picture from Pexels based on the query."""
        key = self.pexels_api_key.get()
        if not key:
            response = "Pexels API key is missing."
        elif not query:
            response = "Please specify a query."
        else:
            url = "https://api.pexels.com/v1/search"
            headers = {
                "Authorization": key
            }
            params = {
                "query": query,
                "per_page": 1,
                "page": 1
            }
            try:
                r = requests.get(url, headers=headers, params=params, timeout=10)
                r.raise_for_status()  # Raise an HTTPError for bad responses
                data = r.json()
                photos = data.get("photos", [])
                if not photos:
                    response = f"No pictures found for '{query}'."
                else:
                    photo = photos[0]
                    photographer = photo.get("photographer", "Unknown")
                    src = photo.get("src", {}).get("original", "No URL")
                    response = f"Photo by {photographer}: {src}"
            except requests.exceptions.RequestException as e:
                response = f"Error fetching picture: {str(e)}"

        self.send_full_message(response)

    def refresh_membership(self):
        """Refresh the membership list by sending an ENTER keystroke and allowing time for processing."""
        self.send_enter_keystroke()
        time.sleep(1)         # Allow BBS lines to arrive
        self.master.update()  # Let process_incoming_messages() parse them

    def get_news_response(self, topic):
        """Fetch top 2 news headlines and return the response as a string."""
        key = self.news_api_key.get()
        if not key:
            return "News API key is missing."
        else:
            url = "https://newsapi.org/v2/everything"  # Using "everything" endpoint for broader topic search
            params = {
                "q": topic,  # The keyword/topic to search for
                "apiKey": key,
                "language": "en",
                "pageSize": 2  # Fetch top 2 headlines
            }
            try:
                r = requests.get(url, params=params)
                data = r.json()
                articles = data.get("articles", [])
                if not articles:
                    return f"No news articles found for '{topic}'."
                else:
                    response = ""
                    for i, article in enumerate(articles):
                        title = article.get("title", "No Title")
                        description = article.get("description", "No Description")
                        link = article.get("url", "No URL")
                        response += f"{i + 1}. {title}\n   {description[:230]}...\n"
                        response += f"Link: {link}\n\n"
                    return response.strip()
            except Exception as e:
                return f"Error fetching news: {str(e)}"

    def handle_polly_command(self, voice, text):
        """Convert text to speech using AWS Polly and provide an S3 link to the MP3 file."""
        valid_voices = {
            "Matthew": "standard",
            "Stephen": "neural",
            "Ruth": "neural",
            "Joanna": "neural",
            "Danielle": "neural"
        }
        if voice not in valid_voices:
            response_message = f"Invalid voice. Please choose from: {', '.join(valid_voices.keys())}."
            self.send_full_message(response_message)
            return

        if len(text) > 200:
            response_message = "Error: The text for Polly must be 200 characters or fewer."
            self.send_full_message(response_message)
            return

        polly_client = boto3.client('polly', region_name='us-east-1')
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'bbs-audio-files'
        object_key = f"polly_output_{int(time.time())}.mp3"

        try:
            response = polly_client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId=voice,
                Engine=valid_voices[voice]
            )
            audio_stream = response['AudioStream'].read()

            s3_client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=audio_stream,
                ContentType='audio/mpeg'
            )

            s3_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
            response_message = f"Here is your Polly audio: {s3_url}"
        except Exception as e:
            response_message = f"Error with Polly: {str(e)}"

        self.send_full_message(response_message)

    def handle_ytmp3_command(self, url):
        try:
            # Enhanced yt-dlp command with bypassing options
            result = subprocess.run([
                "yt-dlp", 
                "-x", 
                "--audio-format", "mp3",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--add-header", "Accept-Language:en-US,en;q=0.9",
                "--geo-bypass",
                "--no-check-certificate",
                url, 
                "-o", "/tmp/%(id)s.%(ext)s"
            ], capture_output=True, text=True)
                
            if result.returncode != 0:
                raise Exception(result.stderr)

            # Extract the video ID from the URL
            video_id = url.split("v=")[1].split("&")[0] if "v=" in url else url.split("/")[-1]
            mp3_filename = f"/tmp/{video_id}.mp3"

            s3_client = boto3.client('s3', region_name='us-east-1')
            bucket_name = 'bbs-audio-files'
            object_key = f"ytmp3_{video_id}.mp3"

            with open(mp3_filename, 'rb') as mp3_file:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=mp3_file,
                    ContentType='audio/mpeg'
                )

            s3_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
            response_message = f"Here is your MP3: {s3_url}"
        except Exception as e:
            response_message = f"Error processing YouTube link: {str(e)}"

        self.send_full_message(response_message)

    def handle_greeting_command(self):
        """Toggle the auto-greeting feature on and off."""
        self.auto_greeting_enabled = not self.auto_greeting_enabled
        state = "enabled" if self.auto_greeting_enabled else "disabled"
        response = f"Auto-greeting has been {state}."
        self.send_full_message(response)

    def handle_seen_command(self, username):
        """Handle the !seen command to report the last seen timestamp of a user."""
        response = self.get_seen_response(username)
        self.send_full_message(response)

    def get_seen_response(self, username):
        """Return the last seen timestamp of a user in GMT time."""
        username_lower = username.lower()
        last_seen_lower = {k.lower(): v for k, v in self.last_seen.items()}

        if username_lower in last_seen_lower:
            last_seen_time = last_seen_lower[username_lower]
            # Convert timestamp to GMT/UTC time
            last_seen_str = time.strftime('%Y-%m-%d %H:%M:%S GMT', time.gmtime(last_seen_time))
            time_diff = int(time.time()) - last_seen_time
            hours, remainder = divmod(time_diff, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{username} was last seen on {last_seen_str} ({hours} hours, {minutes} minutes, {seconds} seconds ago)."
        else:
            return f"{username} has not been seen in the chatroom."

    def save_last_seen(self):
        """Save the last seen dictionary to a file with error handling."""
        try:
            with open("last_seen.json", "w") as file:
                json.dump(self.last_seen, file, indent=2)
            print("[DEBUG] Successfully saved last seen timestamps")
        except Exception as e:
            print(f"[ERROR] Failed to save last seen timestamps: {e}")

    def load_last_seen(self):
        """Load the last seen dictionary from a file with error handling."""
        try:
            if os.path.exists("last_seen.json"):
                with open("last_seen.json", "r") as file:
                    data = json.load(file)
                    # Convert all keys to lowercase for case-insensitive matching
                    return {k.lower(): v for k, v in data.items()}
            return {}
        except Exception as e:
            print(f"[ERROR] Failed to load last seen timestamps: {e}")
            return {}

    def get_stock_price(self, symbol):
        """Fetch the current price of a stock using Yahoo Finance."""
        if not symbol:
            return "Please provide a stock symbol."
        
        try:
            import yfinance as yf
            
            # Get stock data
            ticker = yf.Ticker(symbol)
            
            # Force data download to get latest price
            data = ticker.history(period="1d")
            if data.empty:
                return f"No data found for symbol {symbol}"
                
            # Get the latest price information
            price = data['Close'].iloc[-1]
            
            # Get additional info for percentage change
            prev_close = ticker.info.get('previousClose')
            if prev_close:
                change = price - prev_close
                percent_change = (change / prev_close) * 100
                
                return f"{symbol.upper()}: ${price:.2f} ({change:.2f} | {percent_change:.2f}%)"
            else:
                return f"{symbol.upper()}: ${price:.2f}"
                
        except ImportError:
            return "Yahoo Finance package not installed. Run 'pip install yfinance'."
        except Exception as e:
            return f"Error fetching stock price for {symbol}: {str(e)}"

    def get_crypto_price(self, crypto):
        """Fetch the current price of a cryptocurrency."""
        api_key = self.coinmarketcap_api_key.get()
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol': crypto,
            'convert': 'USD'
        }
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': api_key,
        }
        session = requests.Session()
        session.headers.update(headers)
        try:
            response = session.get(url, params=parameters)
            data = response.json()
            if "data" in data and crypto in data["data"]:
                price = data["data"][crypto]["quote"]["USD"]["price"]
                return f"{crypto.upper()}: ${price:.2f}"
            else:
                return f"Invalid cryptocurrency symbol '{crypto}'. Please use valid symbols like BTC, ETH, DOGE, etc."
        except (requests.ConnectionError, requests.Timeout, requests.TooManyRedirects) as e:
            return f"Error fetching crypto price: {str(e)}"

    def handle_stock_command(self, symbol):
        """Handle the !stocks command to show the current price of a stock."""
        if not self.alpha_vantage_api_key.get():
            response = "Alpha Vantage API key is missing."
        else:
            response = self.get_stock_price(symbol)
        self.send_full_message(response[:50])  # Ensure the response is no more than 50 characters

    def handle_crypto_command(self, crypto):
        """Handle the !crypto command to show the current price of a cryptocurrency."""
        if not self.coinmarketcap_api_key.get():
            response = "CoinMarketCap API key is missing."
        else:
            response = self.get_crypto_price(crypto)
        self.send_full_message(response[:50])  # Ensure the response is no more than 50 characters

    def handle_cleanup_maintenance(self):
        """Handle cleanup maintenance by reconnecting to the BBS."""
        if self.logon_automation_enabled.get():
            print("Cleanup maintenance detected. Reconnecting to the BBS...")
            self.disconnect_from_bbs()
            time.sleep(5)  # Wait for a few seconds before reconnecting
            self.start_connection()

    def handle_timer_command(self, username, value, unit):
        """Handle the !timer command to set a timer for the user."""
        try:
            value = int(value)
            if unit not in ["minutes", "seconds"]:
                raise ValueError("Invalid unit")
        except ValueError:
            self.send_full_message("Invalid timer value or unit. Please use the syntax '!timer <value> <minutes or seconds>'.")
            return

        duration = value * 60 if unit == "minutes" else value
        timer_id = f"{username}_{time.time()}"

        def timer_callback():
            self.send_full_message(f"Timer for {username} has ended.")
            del self.timers[timer_id]

        self.timers[timer_id] = self.master.after(duration * 1000, timer_callback)
        self.send_full_message(f"Timer set for {username} for {value} {unit}.")

    def get_gif_response(self, query):
        """Fetch a popular GIF based on the query and return the direct link to the GIF."""
        key = self.giphy_api_key.get()
        if not key:
            return "Giphy API key is missing."
        elif not query:
            return "Please specify a query."
        else:
            url = "https://api.giphy.com/v1/gifs/search"
            params = {
                "api_key": key,
                "q": query,
                "limit": 1,
                "rating": "g"
            }
            try:
                r = requests.get(url, params=params)
                data = r.json()
                if not data['data']:
                    return "No GIFs found for the query."
                else:
                    gif_page_url = data['data'][0]['url']
                    # Fetch the HTML content of the Giphy page
                    page_response = requests.get(gif_page_url)
                    soup = BeautifulSoup(page_response.content, 'html.parser')
                    # Extract the direct link to the GIF
                    meta_tag = soup.find('meta', property='og:image')
                    if meta_tag:
                        direct_gif_url = meta_tag['content']
                        # Ensure the link ends with .gif
                        if direct_gif_url.endswith('.webp'):
                            direct_gif_url = direct_gif_url.replace('.webp', '.gif')
                        # Shorten the URL
                        shortened_url = self.shorten_url(direct_gif_url)
                        return shortened_url
                    else:
                        return "Could not extract the direct GIF link."
            except requests.exceptions.RequestException as e:
                return f"Error fetching GIF: {str(e)}"

    def toggle_split_view(self):
        """Toggle the split view to create multiple bot instances."""
        if not self.split_view_enabled:
            self.split_view_enabled = True
            main_container = self.master.nametowidget('main_frame')
            main_container.pack-forget()

            split_frame = ttk.Frame(self.master)
            split_frame.pack(fill=tk.BOTH, expand=True)

            left_frame = ttk.Frame(split_frame)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            right_frame = ttk.Frame(split_frame)
            right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

            main_container.pack(in_=left_frame, fill=tk.BOTH, expand=True)
            clone = self.create_clone(main_container)
            clone.pack(in_=right_frame, fill=tk.BOTH, expand=True)

            self.split_view_clones.append(clone)
            print("Split View enabled")
        else:
            self.split_view_enabled = False
            for clone in self.split_view_clones:
                clone.destroy()
            self.split_view_clones.clear()
            main_container = self.master.nametowidget('main_frame')
            main_container.pack(fill=tk.BOTH, expand=True)
            print("Split View disabled")

    def create_clone(self, widget):
        """Create a clone of the given widget."""
        clone = ttk.Frame(self.master)
        for child in widget.winfo_children():
            child_clone = self.clone_widget(child, clone)
            child_clone.pack()
        return clone

    def clone_widget(self, widget, parent):
        """Clone a widget and its configuration."""
        widget_class = widget.__class__
        widget_config = {key: val[-1] for key, val in widget.configure().items() if isinstance(val[-1], (str, int, float)) or key in ('text', 'value')}
        
        # Handle special cases for configuration values
        for key, val in widget_config.items():
            if isinstance(val, str) and val.startswith('-'):
                widget_config[key] = val[1:]
            if key in ('borderwidth', 'highlightthickness', 'padx', 'pady'):
                widget_config[key] = int(val) if val else 0
            if key == 'font':
                font_parts = val.split()
                if len(font_parts) > 1 and font_parts[1].isdigit():
                    widget_config[key] = (font_parts[0], int(font_parts[1]))
                else:
                    widget_config[key] = val
            if key == 'width' and val == 'borderwidth':
                widget_config[key] = 1

        # Ensure valid configuration values
        widget_config = {k: v for k, v in widget_config.items() if v is not None and v != ''}

        # Handle special cases for Text widget
        if widget_class == tk.Text:
            widget_clone = widget_class(parent, **widget_config)
            widget_clone.insert(tk.END, widget.get("1.0", tk.END))
        else:
            widget_clone = widget_class(parent, **widget_config)

        for child in widget.winfo_children():
            self.clone_widget(child, widget_clone)
        return widget_clone

    def handle_msg_command(self, recipient, message, sender):
        """Handle the !msg command to leave a message for another user."""
        # When in no_spam mode, always respond via whisper
        if self.no_spam_mode.get() or self.no_spam_perm:
            self.send_private_message(sender, f"Message for {recipient} saved. They will receive it the next time they are seen in the chatroom.")
        else:
            self.send_full_message(f"Message for {recipient} saved. They will receive it the next time they are seen in the chatroom.")
        self.save_pending_message(recipient, sender, message)

    def check_and_send_pending_messages(self, username):
        """Check for and send any pending messages for the given username."""
        pending_messages = self.get_pending_messages(username)
        for msg in pending_messages:
            sender = msg['sender']
            message = msg['message']
            timestamp = msg['timestamp']
            # Use send_private_message instead of send_direct_message
            self.send_private_message(username, f"Message from {sender}: {message}")
            self.delete_pending_message(username, timestamp)

    def load_no_spam_state(self):
        """Load both nospam states from file."""
        if os.path.exists("nospam_state.json"):
            with open("nospam_state.json", "r") as file:
                data = json.load(file)
                return {
                    'nospam': data.get("nospam", True),
                    'nospam_perm': data.get("nospam_perm", False)
                }
        return {'nospam': True, 'nospam_perm': False}  # Default values

    def save_no_spam_state(self):
        with open("nospam_state.json", "w") as file:
            json.dump({
                "nospam": self.no_spam_mode.get(),
                "nospam_perm": self.no_spam_perm
            }, file, indent=4)

    def handle_doc_command(self, query, username, public=False):
        """Handle the !doc command to create a document using ChatGPT and provide an S3 link to the file."""
        if not query:
            response_message = "Please provide a query for the document."
            # Check no_spam setting when deciding how to respond
            if public and not (self.no_spam_mode.get() or self.no_spam_perm):
                self.send_full_message(response_message)
            else:
                self.send_private_message(username, response_message)
            return

        # Prepare the prompt for ChatGPT
        prompt = f"Please write a detailed, verbose document based on the following query: {query}"

        try:
            # Get the response from ChatGPT
            response = self.get_chatgpt_document_response(prompt)

            # Save the response to a .txt file
            filename = f"document_{int(time.time())}.txt"
            with open(filename, 'w') as file:
                file.write(response)

            # Upload the file to S3
            s3_client = boto3.client('s3', region_name='us-east-1')
            bucket_name = 'bot-files-repo'
            object_key = filename

            with open(filename, 'rb') as file:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=file,
                    ContentType='text/plain'
                )

            # Generate the S3 URL
            s3_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
            response_message = f"Here is your document: {s3_url}"

            # Delete the local file after uploading
            os.remove(filename)

        except Exception as e:
            response_message = f"Error creating document: {str(e)}"

        # Check no_spam setting when deciding how to respond
        if public and not (self.no_spam_mode.get() or self.no_spam_perm):
            self.send_full_message(response_message)
        else:
            self.send_private_message(username, response_message)

    def get_chatgpt_document_response(self, prompt):
        """Send a prompt to ChatGPT and return the full response as a string."""
        if not self.openai_client:
            return "OpenAI client is not initialized."

        messages = [
            {"role": "system", "content": "You are a writer of detailed, verbose documents."},
            {"role": "user", "content": prompt}
        ]

        try:
            completion = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                n=1,
                max_tokens=10000,  # Allow for longer responses
                temperature=0.2,  # Set temperature
                messages=messages
            )
            gpt_response = completion.choices[0].message.content
        except Exception as e:
            gpt_response = f"Error with ChatGPT API: {str(e)}"

        return gpt_response

    def store_public_message(self, username, message):
        """Store the public message for the given username (keeping only the three most recent)."""
        username = username.lower()
        if username not in self.public_message_history:
            self.public_message_history[username] = []
        # Split the message into lines and store each line separately
        lines = message.split('\n')
        for line in lines:
            self.public_message_history[username].append(line)
        if len(self.public_message_history[username]) > 3:
            self.public_message_history[username] = self.public_message_history[username][-3:]

    def handle_said_command(self, sender, command_text, is_page=False, module_or_channel=None):
        """Handle the !said command to report the last three public messages of a user."""
        parts = command_text.split()
        if len(parts) == 1:
            # No username provided, report the last three things said in the chatroom
            all_messages = []
            for user_messages in self.public_message_history.values():
                all_messages.extend(user_messages)
            all_messages = all_messages[-3:]  # Get the last three messages
            if not all_messages:
                response = "No public messages found."
            else:
                response = "Last three public messages in the chatroom: " + " ".join(all_messages)
        elif len(parts) == 2:
            # Username provided, report the last three messages from that user
            target_username = parts[1].lower()
            if target_username not in self.public_message_history:
                response = f"No public messages found for {target_username}."
            else:
                messages = self.public_message_history[target_username][-3:]  # Get the last three messages
                response = f"Last three public messages from {target_username}: " + " ".join(messages)
        else:
            response = "Usage: !said [<username>]"

        if is_page and module_or_channel:
            self.send_page_response(sender, module_or_channel, response)
        else:
            # Check no_spam setting before deciding how to respond
            if self.no_spam_mode.get() or self.no_spam_perm:
                self.send_private_message(sender, response)
            else:
                self.send_full_message(response)

    def handle_public_trigger(self, username, message):
        """
        Handle public message triggers and respond accordingly.
        If !nospam is enabled, respond via whisper instead of public message.
        """
        # Special handling for !nospam command when nospamperm is enabled
        if "!nospam" in message:
            if self.no_spam_perm:
                self.send_private_message(username, "Not possible - No Spam Mode is permanently locked.")
            else:
                self.send_private_message(username, "The !nospam command must be sent via whisper or page.")
            return

        response = None  # Initialize response with None
        
        if "!weather" in message:
            location = message.split("!weather", 1)[1].strip()
            response = self.get_weather_response(location)
        elif "!yt" in message:
            query = message.split("!yt", 1)[1].strip()
            response = self.get_youtube_response(query)
        elif "!search" in message:
            query = message.split("!search", 1)[1].strip()
            response = self.get_web_search_response(query)
        elif "!chat" in message:
            query = message.split("!chat", 1)[1].strip()
            response = self.get_chatgpt_response(query, username=username)
        elif "!news" in message:
            topic = message.split("!news", 1)[1].strip()
            response = self.get_news_response(topic)
        elif "!map" in message:
            place = message.split("!map", 1)[1].strip()
            response = self.get_map_response(place)
        elif "!pic" in message:
            query = message.split("!pic", 1)[1].strip()
            response = self.get_pic_response(query)
        elif "!help" in message:
            help_chunks = self.get_help_response()
            
            def send_delayed_chunk(chunk_index):
                if chunk_index < len(help_chunks):
                    if self.no_spam_mode.get():
                        self.send_private_message(username, help_chunks[chunk_index])
                    else:
                        self.send_full_message(help_chunks[chunk_index])
                    # Schedule next chunk after 1 second
                    self.master.after(1000, lambda: send_delayed_chunk(chunk_index + 1))
            
            # Start sending chunks
            send_delayed_chunk(0)
            return
        elif "!stocks" in message:
            symbol = message.split("!stocks", 1)[1].strip()
            response = self.get_stock_price(symbol)
        elif "!crypto" in message:
            crypto = message.split("!crypto", 1)[1].strip()
            response = self.get_crypto_price(crypto)
        elif "!gif" in message:
            query = message.split("!gif", 1)[1].strip()
            response = self.get_gif_response(query)
        elif "!seen" in message:
            target_username = message.split("!seen", 1)[1].strip()
            response = self.get_seen_response(target_username)
        elif "!doc" in message:
            query = message.split("!doc", 1)[1].strip()
            self.handle_doc_command(query, username, public=not self.no_spam_mode.get())
            return
        elif "!said" in message:
            self.handle_said_command(username, message)
            return
        elif "!pod" in message:
            self.handle_pod_command(username, message)
            return
        elif "!mail" in message:
            self.handle_mail_command(message)
            return
        elif "!blaz" in message:
            call_letters = message.split("!blaz", 1)[1].strip()
            response = self.handle_blaz_command(call_letters)
        elif "!musk" in message:
            response = self.get_musk_post()
        elif "!msg" in message:
            parts = message.split(maxsplit=2)
            if len(parts) < 3:
                response = "Usage: !msg <username> <message>"
                if self.no_spam_mode.get() or self.no_spam_perm:
                    self.send_private_message(username, response)
                else:
                    self.send_full_message(response)
            else:
                recipient = parts[1]
                msg_content = parts[2]
                self.handle_msg_command(recipient, msg_content, username)
            return
        elif "!since" in message:
            parts = message.split("!since", 1)[1].strip()
            response = self.handle_since_command(parts if parts else username)

        if response:
            if self.no_spam_mode.get():
                self.send_private_message(username, response)
            else:
                self.send_full_message(response)

    def handle_pod_command(self, sender, command_text, is_page=False, module_or_channel=None):
        """Handle the !pod command to fetch podcast episode details."""
        match = re.match(r'!pod\s+"([^"]+)"\s+"([^"]+)"', command_text)
        if not match:
            response = 'Usage: !pod "<show>" "<episode name or number>"'
            if is_page and module_or_channel:
                self.send_page_response(sender, module_or_channel, response)
            else:
                # Check no_spam setting before deciding how to respond
                if self.no_spam_mode.get() or self.no_spam_perm:
                    self.send_private_message(sender, response)
                else:
                    self.send_full_message(response)
            return

        show = match.group(1)
        episode = match.group(2)
        response = self.get_podcast_response(show, episode)
        if is_page and module_or_channel:
            self.send_page_response(sender, module_or_channel, response)
        else:
            # Check no_spam setting before deciding how to respond
            if self.no_spam_mode.get() or self.no_spam_perm:
                self.send_private_message(sender, response)
            else:
                self.send_full_message(response)

    def get_podcast_response(self, show, episode):
        """Query the iTunes API for podcast episode details."""
        url = "https://itunes.apple.com/search"
        # Build parameters with a cache-buster parameter
        params = {
            "term": f"{show} {episode}",
            "media": "podcast",
            "entity": "podcastEpisode",
            "limit": 10,  # Increase limit to 10 results
            "cb": int(time.time())  # Cache buster to force a fresh request
        }
        try:
            # Add header to prevent caching
            r = requests.get(url, params=params, headers={"Cache-Control": "no-cache"})
            data = r.json()
            if data["resultCount"] == 0:
                # Retry with just the show name if no results found
                params["term"] = show
                params["cb"] = int(time.time())  # Update cache buster
                r = requests.get(url, params=params, headers={"Cache-Control": "no-cache"})
                data = r.json()
                if data["resultCount"] == 0:
                    return f"No matching episode found for {show} {episode}."

            results = data["results"]
            best_match = None

            # Check if the episode argument is numeric and adjust matching accordingly.
            is_numeric_episode = episode.isdigit()

            for result in results:
                title = result.get("trackName", "").lower()
                description = result.get("description", "").lower()
                if is_numeric_episode:
                    if f"episode {episode}" in title or f"episode {episode}" in description:
                        best_match = result
                        break
                else:
                    if episode.lower() in title or episode.lower() in description:
                        best_match = result
                        break

            if not best_match:
                return f"No matching episode found for {show} {episode}."

            title = best_match.get("trackName", "N/A")
            release_date = best_match.get("releaseDate", "N/A")
            preview_url = best_match.get("previewUrl", "N/A")
            return f"Title: {title}\nRelease Date: {release_date}\nPreview: {preview_url}"
        except Exception as e:
            return f"Error fetching podcast details: {str(e)}"

    def get_trump_post(self):
        """Run the Trump post scraper script and return the latest post."""
        try:
            script_path = "/home/ec2-user/Headless-Robot/TrumpsLatestPostScraper.py"
            command = [sys.executable, script_path]
            
            # Verify script exists before running
            if not os.path.exists(script_path):
                return f"Error: Script not found at {script_path}"
                
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', 
                                  errors='ignore', timeout=180)
            output = result.stdout.strip()

            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown error from Trump scraper."
                return f"Error from Trump post script: {error_msg}"

            # Split the output into lines and get the last two lines
            lines = output.splitlines()
            if len(lines) >= 2:
                return "\n".join(lines[-2:])
            else:
                return output
        except Exception as e:
            return f"Error running Trump post script: {str(e)}"

    def load_email_credentials(self):
        """Load email credentials from a file."""
        if os.path.exists("email_credentials.json"):
            with open("email_credentials.json", "r") as file:
                return json.load(file)
        return {}

    def send_email(self, recipient, subject, body, sender_username=None):
        """Send an email using Gmail."""
        credentials = self.load_email_credentials()
        smtp_server = credentials.get("smtp_server", "smtp.gmail.com")
        smtp_port = credentials.get("smtp_port", 587)
        sender_email = credentials.get("sender_email")
        sender_password = credentials.get("sender_password")

        if not sender_email or not sender_password:
            return "Email credentials are missing."

        try:
            # Add signature if sender_username is provided
            if sender_username:
                body += f"\n\n--\nSent from BBS user {sender_username}"
                
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = sender_email
            msg["To"] = recipient

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, [recipient], msg.as_string())

            return f"Email sent to {recipient} successfully."
        except Exception as e:
            return f"Error sending email: {str(e)}"





    def check_incoming_mail(self):
        """
        Periodically check for incoming emails with the subject 'BBS'.
        If found, post their content to the BBS chatroom.
        """
        if not self.connected:
            # Skip if not connected to BBS
            self.master.after(60000, self.check_incoming_mail)  # Check again in 1 minute
            return

        credentials = self.load_email_credentials()
        email_address = credentials.get("sender_email")
        password = credentials.get("sender_password")

        if not email_address or not password:
            print("Email credentials are missing. Cannot check incoming mail.")
            self.master.after(60000, self.check_incoming_mail)  # Check again in 1 minute
            return

        try:
            # Connect to the IMAP server
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(email_address, password)
            mail.select('inbox')

            # Search for unread emails with subject 'BBS'
            status, messages = mail.search(None, '(UNSEEN SUBJECT "BBS")')

            if status != 'OK':
                print(f"Error searching for messages: {status}")
                mail.logout()
                self.master.after(60000, self.check_incoming_mail)  # Check again in 1 minute
                return

            # Process each matching email
            for num in messages[0].split():
                status, data = mail.fetch(num, '(RFC822)')
                if status != 'OK':
                    print(f"Error fetching message {num}: {status}")
                    continue

                email_msg = email.message_from_bytes(data[0][1])
                sender = parseaddr(email_msg['From'])[1]

                # Get the message body
                body = ""
                if email_msg.is_multipart():
                    for part in email_msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            body = part.get_payload(decode=True).decode('utf-8')
                            break
                else:
                    body = email_msg.get_payload(decode=True).decode('utf-8')

                # Truncate to 230 characters if needed
                if len(body) > 230:
                    body = body[:227] + "..."

                # Post to BBS chatroom
                self.send_full_message(f"Email from {sender}: {body}")

                # Mark the email as read
                mail.store(num, '+FLAGS', '\\Seen')

            mail.logout()
        except Exception as e:
            print(f"Error checking incoming mail: {e}")

        # Schedule next check
        self.master.after(30000, self.check_incoming_mail)  # Check every 30 seconds






    def handle_mail_command(self, command_text):
        """Handle the !mail command to send an email."""
        try:
            # Extract the sender's username from command_text
            sender_match = re.match(r'From (.+?): !mail', command_text)
            sender_username = sender_match.group(1) if sender_match else "Unknown User"
            
            parts = shlex.split(command_text)
            if len(parts) < 4:
                response = "Usage: !mail \"recipient@example.com\" \"Subject\" \"Body\""
                # Check no_spam setting before deciding how to respond
                if self.no_spam_mode.get() or self.no_spam_perm:
                    if sender_username != "Unknown User":
                        self.send_private_message(sender_username, response)
                    else:
                        self.send_full_message(response)
                else:
                    self.send_full_message(response)
                return

            recipient = parts[1]
            subject = parts[2]
            body = parts[3]
            response = self.send_email(recipient, subject, body, sender_username)
            
            # Check no_spam setting before deciding how to respond
            if self.no_spam_mode.get() or self.no_spam_perm:
                if sender_username != "Unknown User":
                    self.send_private_message(sender_username, response)
                else:
                    self.send_full_message(response)
            else:
                self.send_full_message(response)
        except ValueError as e:
            error_response = f"Error parsing command: {str(e)}"
            # Same check for response
            if self.no_spam_mode.get() or self.no_spam_perm:
                sender_match = re.match(r'From (.+?): !mail', command_text)
                sender_username = sender_match.group(1) if sender_match else None
                if sender_username:
                    self.send_private_message(sender_username, error_response)
                else:
                    self.send_full_message(error_response)
            else:
                self.send_full_message(error_response)

    def get_pic_response(self, query):
        """Fetch a picture or GIF URL based on the query format '!pic <img/gif> <search terms>'."""
        if not query:
            return "Usage: !pic <img/gif> <search terms>"

        # Split the query into type and search terms
        parts = query.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: !pic <img/gif> <search terms>"

        pic_type, search_terms = parts[0].lower(), parts[1]

        if pic_type not in ["img", "gif"]:
            return "Invalid type. Use 'img' for images or 'gif' for GIFs."

        cse_key = self.google_cse_api_key.get()
        cse_id = self.google_cse_pic_cx.get()
        if not cse_key or not cse_id:
            return "Google CSE API key or engine ID is missing."

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": cse_key,
            "cx": cse_id,
            "q": search_terms,
            "searchType": "image",
            "num": 1
        }

        # Add filetype restriction based on type
        if pic_type == "gif":
            params["fileType"] = "gif"
        elif pic_type == "img":
            params["fileType"] = "jpg,png"

        try:
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            items = data.get("items", [])
            if not items:
                return f"No {pic_type}s found for '{search_terms}'."
            
            # Get the image direct link - use image.link for more reliable direct access
            item = items[0]
            if "image" in item and "url" in item.get("image", {}):
                # Use the image.url field which is more likely to be a direct image link
                image_url = item["image"]["url"]
            else:
                # Fallback to the link field if image.url is not available
                image_url = item["link"]
            
            # For images, ensure we have a direct image URL (ends with image extension)
            if pic_type == "img" and not any(image_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                # If not a direct image URL, try the thumbnailLink which is usually direct
                if "image" in item and "thumbnailLink" in item.get("image", {}):
                    image_url = item["image"]["thumbnailLink"]
            
            # Shorten URL with error handling
            try:
                shortened_url = self.shorten_url(image_url)
                if shortened_url and "tinyurl.com" in shortened_url:
                    final_url = shortened_url
                else:
                    # If shortening failed, use original URL
                    final_url = image_url
            except Exception:
                final_url = image_url
                
            return f"{pic_type.upper()} result for '{search_terms}': {final_url}"

        except requests.exceptions.RequestException as e:
            return f"Error fetching {pic_type}: {str(e)}"
        except Exception as e:
            return f"Unexpected error processing {pic_type} request: {str(e)}"

    def handle_blaz_command(self, call_letters):
        """Handle the !blaz command to provide radio station's live broadcast link."""
        radio_links = {
            "WPBG": "https://playerservices.streamtheworld.com/api/livestream-redirect/WPBGFM.mp3",
            "WSWT": "https://playerservices.streamtheworld.com/api/livestream-redirect/WSWTFM.mp3",
            "WMBD": "https://playerservices.streamtheworld.com/api/livestream-redirect/WMBDAM.mp3",
            "WIRL": "https://playerservices.streamtheworld.com/api/livestream-redirect/WIRLAM.mp3",
            "WXCL": "https://playerservices.streamtheworld.com/api/livestream-redirect/WXCLFM.mp3",
            "WKZF": "https://playerservices.streamtheworld.com/api/livestream-redirect/WKZFFM.mp3"
        }
        
        if not call_letters:
            available_stations = ", ".join(sorted(radio_links.keys()))
            return f"Usage: !blaz <call_letters> | Available stations: {available_stations}"
        
        stream_link = radio_links.get(call_letters.upper(), "No matching radio station found.")
        return f"Listen to {call_letters.upper()} live: {stream_link}"

    def handle_radio_command(self, query):
        """Handle the !radio command to provide an internet radio station link based on the search query."""
        if not query:
            response = "Please provide a search query in quotes, e.g., !radio \"classic rock\"."
        else:
            # Example implementation using a predefined list of radio stations
            radio_stations = {
                "classic rock": "https://www.classicrockradio.com/stream",
                "jazz": "https://www.jazzradio.com/stream",
                "pop": "https://www.popradio.com/stream",
                "news": "https://www.newsradio.com/stream"
            }
            station_link = radio_stations.get(query.lower(), "No matching radio station found.")
            response = f"Radio station for '{query}': {station_link}"
        self.send_full_message(response)

    def get_musk_post(self):
        """Run the Musk post scraper script and return the latest post."""
        try:
            script_path = "/home/ec2-user/Headless-Robot/MusksLatestPostScraper.py"
            command = [sys.executable, script_path]
            
            # Verify script exists before running
            if not os.path.exists(script_path):
                return f"Error: Script not found at {script_path}"
                
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', 
                                  errors='ignore', timeout=180)
            output = result.stdout.strip()

            if result.returncode != 0:
                # If the script returned a non-zero exit code
                error_msg = result.stderr.strip() or "Unknown error from Musk scraper."
                return f"Error from Musk post script: {error_msg}"

            # Split the output into lines and get the last line
            lines = output.splitlines()
            if len(lines) >= 1:
                return lines[-1]
            else:
                return output
        except Exception as e:
            return f"Error running Musk post script: {str(e)}"

    def start_join_timer(self):
        """Start timer to send 'join majorlink' every 60 seconds"""
        if self.connected and self.writer:
            asyncio.run_coroutine_threadsafe(self._send_message("join majorlink\r\n"), self.loop)
            self.join_timer = self.master.after(60000, self.start_join_timer)  # Schedule next join

    def stop_join_timer(self):
        """Stop the join timer if it's running"""
        if self.join_timer:
            self.master.after_cancel(self.join_timer)
            self.join_timer = None

    def shorten_url(self, url):
        """Shorten a URL using TinyURL's API with special handling for image URLs."""
        try:
            # Special handling for image URLs - DON'T use TinyURL for these
            if "jpg" in url.lower() or "jpeg" in url.lower() or "png" in url.lower() or "gif" in url.lower() or "image" in url.lower():
                # For images, use a different URL shortener that's more reliable
                # Using is.gd instead of TinyURL for images
                isgd_api = f"https://is.gd/create.php?format=simple&url={requests.utils.quote(url, safe='')}"
                response = requests.get(isgd_api, timeout=5)
                
                if response.status_code == 200:
                    shortened = response.text.strip()
                    if shortened.startswith("https://is.gd/") and len(shortened) < 30:
                        print(f"Successfully shortened image URL with is.gd: {shortened}")
                        return shortened
                
                # If is.gd fails, return original URL for images
                print(f"Using original URL for image: {url}")
                return url
                
            # Standard TinyURL for non-image URLs
            encoded_url = requests.utils.quote(url, safe='')
            tinyurl_api = f"http://tinyurl.com/api-create.php?url={encoded_url}"
            response = requests.get(tinyurl_api, timeout=5)
            
            if response.status_code == 200:
                shortened = response.text.strip()
                
                # Very strict validation
                if shortened.startswith(("https://tinyurl.com/", "http://tinyurl.com/")) and \
                   all(c.isalnum() or c in "-_./:~" for c in shortened):
                    return shortened
            
            # Default fallback to original URL
            print(f"Failed to create valid short URL, using original: {url}")
            return url
            
        except Exception as e:
            print(f"URL shortening error: {e}")
            return url

    def get_gif_response(self, query):
        """Fetch a popular GIF based on the query and return the direct link to the GIF."""
        key = self.giphy_api_key.get()
        if not key:
            return "Giphy API key is missing."
        elif not query:
            return "Please specify a query."
        else:
            url = "https://api.giphy.com/v1/gifs/search"
            params = {
                "api_key": key,
                "q": query,
                "limit": 1,
                "rating": "g"
            }
            try:
                r = requests.get(url, params=params)
                data = r.json()
                if not data['data']:
                    return "No GIFs found for the query."
                else:
                    gif_page_url = data['data'][0]['url']
                    # Fetch the HTML content of the Giphy page
                    page_response = requests.get(gif_page_url)
                    soup = BeautifulSoup(page_response.content, 'html.parser')
                    # Extract the direct link to the GIF
                    meta_tag = soup.find('meta', property='og:image')
                    if meta_tag:
                        direct_gif_url = meta_tag['content']
                        # Ensure the link ends with .gif
                        if direct_gif_url.endswith('.webp'):
                            direct_gif_url = direct_gif_url.replace('.webp', '.gif')
                        # Shorten the URL
                        shortened_url = self.shorten_url(direct_gif_url)
                        return shortened_url
                    else:
                        return "Could not extract the direct GIF link."
            except requests.exceptions.RequestException as e:
                return f"Error fetching GIF: {str(e)}"

    def determine_response_channel(self, message_type, nospam_state, nospam_perm):
        """Determine the appropriate response channel based on message type and nospam states."""
        if message_type in ['whisper', 'page']:
            return message_type  # Always respond in same channel
        elif nospam_state or nospam_perm:
            return 'whisper'     # Force private responses
        else:
            return message_type  # Use original channel

    def parse_message(self, line):
        """Parse incoming messages and return tuple of (type, username, content)."""
        # Remove ANSI codes for easier parsing
        ansi_escape_regex = re.compile(r'\x1b\[(.*?)m')
        clean_line = ansi_escape_regex.sub('', line)

        # Define patterns with their corresponding message types - now supporting both formats
        patterns = {
            # Existing patterns with "From" prefix
            'page': [(r'(.+?) is paging you from (.+?): (.+)', 
                    lambda m: ('page', m.group(1), m.group(3)))],
                    
            'whisper': [(r'From (.+?) \(whispered\): (.+)',
                        lambda m: ('whisper', m.group(1), m.group(2))),
                       # New whisper patterns with :[] format
                       (r':\[(.+?)\] \(whispered\): (.+)',
                        lambda m: ('whisper', m.group(1), m.group(2))),
                       (r':\[(.+?@.+?)\] \(whispered\): (.+)',
                        lambda m: ('whisper', m.group(1), m.group(2)))],
                        
            'direct': [(r'From (.+?) \(to you\): (.+)',
                       lambda m: ('direct', m.group(1), m.group(2))),
                      # New direct message patterns with :[] format
                      (r':\[(.+?)\] \(to you\): (.+)',
                       lambda m: ('direct', m.group(1), m.group(2))),
                      (r':\[(.+?@.+?)\] \(to you\): (.+)',
                       lambda m: ('direct', m.group(1), m.group(2)))],
                       
            'public': [(r'From (.+?): (.+)',
                       lambda m: ('public', m.group(1), m.group(2))),
                      # New public message patterns with :[] format
                      (r':\[(.+?)\]: (.+)',
                       lambda m: ('public', m.group(1), m.group(2))),
                      (r':\[(.+?@.+?)\]: (.+)', 
                       lambda m: ('public', m.group(1), m.group(2)))],
                       
            'third_party': [(r':\[(.+?)\] \(to (.+?)\): (.+)',
                            lambda m: ('third_party', m.group(1), m.group(3))),
                           (r':\[(.+?@.+?)\] \(to (.+?@.+?)\): (.+)',
                            lambda m: ('third_party', m.group(1), m.group(3)))]
        }

        # Process each message type and its patterns
        for msg_type, pattern_list in patterns.items():
            for pattern, extract in pattern_list:
                if match := re.match(pattern, clean_line):
                    msg_type, username, content = extract(match)
                    # Ignore public messages containing 'ultron' if from someone else
                    if msg_type == 'public' and 'ultron' in content.lower() and not username.lower().startswith('ultron'):
                        return None, None, None
                    return msg_type, username, content.strip()

        return None, None, None

    def process_message(self, msg_type, username, content):
        """Process messages according to type and content."""
        if not msg_type or not username or not content:
            return

        content = content.strip()
        
        # Handle nospam commands
        if content == "!nospamperm":
            if msg_type == 'whisper':
                self.no_spam_perm = not self.no_spam_perm  
                state = "permanently enabled" if self.no_spam_perm else "disabled"
                self.send_private_message(username, f"No Spam Mode has been {state}.")
                self.save_no_spam_state()
            else:
                self.send_private_message(username, "The !nospamperm command must be sent via whisper.")
            return

        if content == "!nospam":
            if self.no_spam_perm:
                self.send_private_message(username, "Not possible - No Spam Mode is permanently locked.")
            else:
                self.no_spam_mode.set(not self.no_spam_mode.get())
                state = "enabled" if self.no_spam_mode.get() else "disabled"
                self.send_private_message(username, f"No Spam Mode has been {state}.")
                self.save_no_spam_state()
            return

        # Handle different message types
        if msg_type == 'page':
            if content.startswith('!'):
                response = self.get_command_response(content, username)
            else:
                response = self.get_chatgpt_response(content, username=username)
            if response:
                self.send_page_response(username, 'teleconference', response)
                
        elif msg_type == 'whisper':
            if content.startswith('!'):
                response = self.get_command_response(content, username)
            else:
                response = self.get_chatgpt_response(content, username=username)
            if response:
                self.send_private_message(username, response)
                
        elif msg_type == 'direct':
            if content.startswith('!'):
                response = self.get_command_response(content, username)
            else:
                response = self.get_chatgpt_response(content, username=username)
            if response:
                if self.no_spam_mode.get() or self.no_spam_perm:
                    self.send_private_message(username, response)
                else:
                    self.send_direct_message(username, response)
                
        elif msg_type == 'public':
            if content.startswith('!'):
                response = self.get_command_response(content, username)
                if response:
                    if self.no_spam_mode.get() or self.no_spam_perm:
                        self.send_private_message(username, response)
                    else:
                        self.send_full_message(response)

    def send_page_response(self, username, channel, message):
        """Send a page response via /p command."""
        chunks = self.chunk_message(message, 250)
        for chunk in chunks:
            full_message = f"/p {username} {chunk}"
            asyncio.run_coroutine_threadsafe(self._send_message(full_message + "\r\n"), self.loop)
            time.sleep(0.5)  # Add delay between chunks

    def send_private_message(self, username, message):
        """Send a private message with proper error handling and no recursion."""
        if not message or not username:
            return

        try:
            if isinstance(message, list):
                message = "\n".join(message)
                
            chunks = self.chunk_message(message, 200)
            for i, chunk in enumerate(chunks):
                if self.connected and self.writer:
                    full_message = f"Whisper to {username} {chunk}"
                    # Use asyncio.run_coroutine_threadsafe with timeout
                    future = asyncio.run_coroutine_threadsafe(
                        self._send_message(full_message + "\r\n"), 
                        self.loop
                    )
                    # Wait for the message to be sent with timeout
                    future.result(timeout=3.0)
                    
                    # Log success but don't try to send again
                    self.append_terminal_text(full_message + "\n", "normal")
                    
                    if i < len(chunks) - 1:
                        time.sleep(0.5)
        except Exception as e:
            print(f"Error sending private message: {str(e)}")
            # Don't try to send error message to avoid potential infinite loop

    def send_direct_message(self, username, message):
        """Send a direct public message."""
        chunks = self.chunk_message(message, 250)
        for chunk in chunks:
            full_message = f">{username} {chunk}"
            asyncio.run_coroutine_threadsafe(self._send_message(full_message + "\r\n"), self.loop)
            time.sleep(0.5)  # Add delay between chunks

    def send_full_message(self, message):
        """Send a public message."""
        chunks = self.chunk_message(message, 250)
        for chunk in chunks:
            asyncio.run_coroutine_threadsafe(self._send_message(chunk + "\r\n"), self.loop)
            time.sleep(0.5)  # Add delay between chunks

    def get_command_response(self, content, username=None):
        """Get appropriate response for a command."""
        if not content.startswith('!'):
            return None

        command = content.split()[0][1:]  # Remove ! and get command name
        args = content[len(command)+2:].strip()  # Get everything after command

        # Remove nospamperm handling from here since it should only be handled in whisper
        if command == 'nospamperm':
            return None  # Let process_message handle it
        

        command_handlers = {
            'weather': lambda: self.get_weather_response(args),
            'yt': lambda: self.get_youtube_response(args),
            'search': lambda: self.get_web_search_response(args),
            'chat': lambda: self.get_chatgpt_response(args, username=username),
            'news': lambda: self.get_news_response(args),
            'map': lambda: self.get_map_response(args),
            'pic': lambda: self.get_pic_response(args),
            'help': lambda: self.get_help_response(),
            'seen': lambda: self.get_seen_response(args),
            'stocks': lambda: self.get_stock_price(args.strip()),
            'crypto': lambda: self.get_crypto_price(args),
            'gif': lambda: self.get_gif_response(args),
            'musk': lambda: self.get_musk_post(),
            'trump': lambda: self.get_trump_post(),
            'polly': lambda: self.handle_polly_command(*args.split(maxsplit=1)) if len(args.split(maxsplit=1)) == 2 else "Usage: !polly <voice> <text>",
            'mp3yt': lambda: self.handle_ytmp3_command(args),
            'greeting': lambda: self.handle_greeting_command(),
            'timer': lambda: self.handle_timer_command(username, *args.split(maxsplit=1)) if len(args.split(maxsplit=1)) == 2 else "Usage: !timer <value> <minutes or seconds>",
            'doc': lambda: self.handle_doc_command(args, username),
            'pod': lambda: self.handle_pod_command(username, f"!pod {args}"),
            'said': lambda: self.handle_said_command(username, f"!said {args}"),
            'mail': lambda: self.handle_mail_command(f"!mail {args}"),
            'blaz': lambda: self.handle_blaz_command(args),
            'radio': lambda: self.handle_radio_command(args),
            'msg': lambda: self.handle_msg_command(*args.split(maxsplit=1), username) if len(args.split(maxsplit=1)) == 2 else "Usage: !msg <username> <message>",
            'nospam': lambda: self.no_spam_mode.set(not self.no_spam_mode.get()) or f"No Spam Mode has been {'enabled' if self.no_spam_mode.get() else 'disabled'}.",
            'nospamperm': lambda: "This command is only available via whisper.",
            'since': lambda: self.handle_since_command(args if args else username)
        }

        handler = command_handlers.get(command)
        return handler() if handler else None

        



    def handle_since_command(self, username):
        """Handle the !since command to report when a user was last seen and last spoke."""
        try:
            # Strip domain part if present
            base_username = username.split('@')[0]
            username_lower = base_username.lower()

            # Create case-insensitive mappings with base usernames (no domains)
            last_seen_lower = {k.split('@')[0].lower(): v for k, v in self.last_seen.items()}
            last_spoke_lower = {k.split('@')[0].lower(): v for k, v in self.last_spoke.items()}

            # Get last seen time
            if username_lower in last_seen_lower:
                last_seen_time = last_seen_lower[username_lower]
                last_seen_str = time.strftime('%Y-%m-%d %H:%M:%S GMT', time.gmtime(last_seen_time))
                seen_diff = int(time.time()) - last_seen_time
                seen_hours, seen_remainder = divmod(seen_diff, 3600)
                seen_minutes, seen_seconds = divmod(seen_remainder, 60)
                last_seen_str += f" ({seen_hours}h {seen_minutes}m {seen_seconds}s ago)"
            else:
                last_seen_str = "never"

            # Get last spoke time
            if username_lower in last_spoke_lower:
                last_spoke_time = last_spoke_lower[username_lower]
                last_spoke_str = time.strftime('%Y-%m-%d %H:%M:%S GMT', time.gmtime(last_spoke_time))
                spoke_diff = int(time.time()) - last_spoke_time
                spoke_hours, spoke_remainder = divmod(spoke_diff, 3600)
                spoke_minutes, spoke_seconds = divmod(spoke_remainder, 60)
                last_spoke_str += f" ({spoke_hours}h {spoke_minutes}m {spoke_seconds}s ago)"
            else:
                last_spoke_str = "never"

            # Create single response string
            response = f"{base_username} - Last seen: {last_seen_str} | Last spoke: {last_spoke_str}"
            return response

        except Exception as e:
            print(f"Error in handle_since_command: {str(e)}")
            return f"Error processing !since command for {username}"

    def load_last_spoke(self):
        """Load the last spoke dictionary from a file."""
        if os.path.exists("last_spoke.json"):
            with open("last_spoke.json", "r") as file:
                return json.load(file)
        return {}

    def save_last_spoke(self):
        """Save the last spoke dictionary to a file."""
        with open("last_spoke.json", "w") as file:
            json.dump(self.last_spoke, file)

def main():
    app = None  # Ensure app is defined
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
        root = tk.Tk()
        app = BBSBotApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("Script interrupted by user. Exiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if app and app.connected:
            try:
                asyncio.run_coroutine_threadsafe(app.disconnect_from_bbs(), app.loop).result()
            except Exception as e:
                print(f"Error during disconnect: {e}")
        try:
            if root.winfo_exists():
                root.quit()
        except tk.TclError:
            pass
        finally:
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    loop.close()
            except Exception as e:
                print(f"Error closing event loop: {e}")

if __name__ == "__main__":
    main()

