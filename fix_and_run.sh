#!/bin/bash

# Convert Windows line endings to Unix
sed -i 's/\r$//' TrumpsLatestPostScraper.py

# Make sure the script is executable
chmod +x TrumpsLatestPostScraper.py

# Run the script
python3 TrumpsLatestPostScraper.py
