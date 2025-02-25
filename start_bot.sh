#!/bin/bash

# Go to project directory
cd /home/ec2-user/Headless-Robot

# Activate virtual environment
source venv/bin/activate

# Start the bot in screen session
screen -dmS bbs_bot python3 UltronCLI.py