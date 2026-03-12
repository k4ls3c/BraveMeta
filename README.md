# BraveMeta

A metadata harvester that uses Brave Search API to find and extract metadata from documents.

## Quick Start

```bash
# Install
pip3 install requests
sudo apt install exiftool  # or brew install exiftool on macOS

# Clone
git clone https://github.com/k4ls3c/BraveMeta.git
cd BraveMeta

# Get API key from https://brave.com/search/api/

# Run
python3 BraveMeta.py -d example.com -k YOUR_API_KEY -o loot
