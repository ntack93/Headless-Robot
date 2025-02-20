#!/bin/bash

set -e  # Exit on error

echo "Installing Google Chrome..."
# Import Google's GPG key
sudo rpm --import https://dl.google.com/linux/linux_signing_key.pub

# Create repo file for Google Chrome
cat << EOF | sudo tee /etc/yum.repos.d/google-chrome.repo
[google-chrome]
name=google-chrome
baseurl=https://dl.google.com/linux/chrome/rpm/stable/x86_64
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
EOF

# Clean yum cache and install Chrome
sudo yum clean all
sudo yum install -y google-chrome-stable

echo "Installing ChromeDriver..."
# Get Chrome version and download matching ChromeDriver
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1)
echo "Chrome version detected: ${CHROME_VERSION}"

# For Chrome 115+ use the new download URL format
if [ "$CHROME_VERSION" -ge "115" ]; then
    # Get the latest driver version for your OS and Chrome version
    LATEST_VERSION_URL="https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION}"
    DRIVER_VERSION=$(curl -s "$LATEST_VERSION_URL")
    
    echo "Downloading ChromeDriver version ${DRIVER_VERSION}..."
    DOWNLOAD_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip"
    wget -O chromedriver_linux64.zip "$DOWNLOAD_URL"
else
    # Legacy download method for older versions
    DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}")
    echo "Downloading ChromeDriver version ${DRIVER_VERSION}..."
    wget -O chromedriver_linux64.zip \
        "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip"
fi

if [ ! -f chromedriver_linux64.zip ]; then
    echo "Failed to download ChromeDriver"
    exit 1
fi

echo "Extracting ChromeDriver..."
unzip -o chromedriver_linux64.zip

# Handle new directory structure for Chrome 115+
if [ -d "chromedriver-linux64" ]; then
    sudo mv -f chromedriver-linux64/chromedriver /usr/bin/
    rm -rf chromedriver-linux64
else
    sudo mv -f chromedriver /usr/bin/
fi

sudo chown root:root /usr/bin/chromedriver
sudo chmod +x /usr/bin/chromedriver

# Cleanup
rm -f chromedriver_linux64.zip

echo "Verifying installation..."
google-chrome --version
chromedriver --version

echo "Installation complete!"
