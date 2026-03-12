#!/usr/bin/env python3
"""
Brave Meta Harvester v2.0 - Metadata Focused Edition
Searches Brave for files, downloads them, and extracts metadata with exiftool
"""

import os
import csv
import time
import json
import argparse
import requests
import subprocess
from urllib.parse import quote, urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from datetime import datetime

class BraveMetaHarvester:
    def __init__(self, domain, api_key, output_dir="loot", max_results=100, threads=5, delay=1):
        self.domain = domain
        self.api_key = api_key
        self.output_dir = output_dir
        self.max_results = max_results
        self.threads = threads
        self.delay = delay
        # Metadata-rich file types only
        self.file_types = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']
        self.results = []
        self.downloaded_files = []
        self.session = requests.Session()
        
        # Brave Search API endpoint
        self.api_url = "https://api.search.brave.com/res/v1/web/search"
        
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'downloads'), exist_ok=True)

    def search_brave(self, filetype, offset=0):
        """Search Brave API for specific filetype"""
        urls = []
        query = f"site:{self.domain} filetype:{filetype}"
        
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }
        
        params = {
            "q": query,
            "count": 20,
            "offset": offset,
            "safesearch": "off",
            "search_lang": "en",
            "country": "us",
            "text_format": "raw"
        }
        
        try:
            print(f"[*] Brave {filetype} - Searching...")
            response = self.session.get(
                self.api_url,
                headers=headers,
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for result in data.get('web', {}).get('results', []):
                    url = result.get('url')
                    if url and f'.{filetype}' in url.lower() and self.domain in url:
                        urls.append(url)
                        print(f"[+] Found: {url}")
                
                # Pagination for more results
                if len(urls) >= 20 and offset < self.max_results:
                    time.sleep(self.delay)
                    urls.extend(self.search_brave(filetype, offset + 20))
            else:
                print(f"[!] Brave API returned {response.status_code}")
                
        except Exception as e:
            print(f"[!] Search error: {e}")
        
        return urls

    def download_file(self, url):
        """Download a single file for metadata extraction"""
        try:
            # Get filename from URL
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename or '.' not in filename:
                filename = f"file_{hash(url)}.{url.split('.')[-1].split('?')[0]}"
            
            # Clean filename
            filename = "".join(c for c in filename if c.isalnum() or c in '.-_').strip()
            filepath = os.path.join(self.output_dir, 'downloads', filename)
            
            # Skip if already downloaded
            if os.path.exists(filepath):
                print(f"[=] Already exists: {filename}")
                return filepath
            
            print(f"[↓] Downloading: {filename}")
            response = self.session.get(url, timeout=30, stream=True)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"[✓] Saved: {filename}")
                return filepath
            else:
                print(f"[!] Failed ({response.status_code}): {url}")
                
        except Exception as e:
            print(f"[!] Download error: {e}")
        
        return None

    def extract_metadata(self, filepath):
        """Extract metadata using exiftool - pure metadata only"""
        try:
            # Run exiftool and get JSON output
            result = subprocess.run(
                ['exiftool', '-json', '-All', filepath],  # -All gets all metadata
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                metadata = json.loads(result.stdout)[0]
                
                # Filter to ONLY metadata fields (remove file system data)
                metadata_only = {}
                exclude_fields = ['SourceFile', 'FileName', 'FileSize', 'FileModifyDate', 
                                 'FileAccessDate', 'FileInodeChangeDate', 'FilePermissions',
                                 'FileType', 'FileTypeExtension', 'MIMEType']
                
                for key, value in metadata.items():
                    if key not in exclude_fields and value and str(value).strip():
                        metadata_only[key] = value
                
                return metadata_only
        except Exception as e:
            print(f"[!] Metadata extraction failed: {e}")
        
        return None

    def analyze_metadata(self, metadata_results):
        """Quick analysis of interesting metadata findings"""
        if not metadata_results:
            return
        
        print("\n" + "="*60)
        print("📊 METADATA SUMMARY")
        print("="*60)
        
        # Track interesting fields
        authors = set()
        creators = set()
        companies = set()
        software = set()
        
        for m in metadata_results:
            if m.get('Author'): authors.add(m['Author'])
            if m.get('Creator'): creators.add(m['Creator'])
            if m.get('Company'): companies.add(m['Company'])
            if m.get('Producer'): software.add(m['Producer'])
            if m.get('LastModifiedBy'): authors.add(m['LastModifiedBy'])
        
        # Display findings
        if authors:
            print(f"\n👤 Authors Found:")
            for a in sorted(authors)[:10]:
                print(f"  • {a}")
        
        if companies:
            print(f"\n🏢 Companies/Departments:")
            for c in sorted(companies)[:10]:
                print(f"  • {c}")
        
        if creators:
            print(f"\n✍️ Creators:")
            for c in sorted(creators)[:10]:
                print(f"  • {c}")
        
        if software:
            print(f"\n💻 Software Used:")
            for s in sorted(software)[:10]:
                print(f"  • {s}")
        
        # Email pattern detection
        emails = set()
        for m in metadata_results:
            for value in m.values():
                if isinstance(value, str) and '@' in value and '.' in value:
                    emails.add(value)
        
        if emails:
            print(f"\n📧 Email Addresses Found:")
            for e in sorted(emails)[:10]:
                print(f"  • {e}")

    def run(self):
        """Main execution - metadata only focus"""
        print(f"""
╔══════════════════════════╗
║   Brave Meta Harvester   ║
╚══════════════════════════╝
        """)
        print(f"[*] Target: {self.domain}")
        print(f"[*] File Types: {', '.join(self.file_types)}")
        print(f"[*] Output: {self.output_dir}\n")

        # Step 1: Search for files
        all_urls = []
        for ft in self.file_types:
            print(f"\n[*] Searching for .{ft} files...")
            urls = self.search_brave(ft)
            all_urls.extend(urls)
            time.sleep(self.delay)

        # Remove duplicates
        all_urls = list(set(all_urls))
        print(f"\n[*] Total unique files found: {len(all_urls)}")

        # Save URLs (for reference)
        with open(os.path.join(self.output_dir, 'urls.txt'), 'w') as f:
            for url in all_urls:
                f.write(url + '\n')

        # Step 2: Download files
        if all_urls:
            print(f"\n[*] Downloading files for metadata extraction...")
            
            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                futures = {executor.submit(self.download_file, url): url 
                          for url in all_urls[:self.max_results]}
                
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        self.downloaded_files.append(result)
                    time.sleep(0.2)

        # Step 3: Extract metadata
        if self.downloaded_files:
            print(f"\n[*] Extracting metadata from {len(self.downloaded_files)} files...")
            
            metadata_results = []
            for filepath in self.downloaded_files:
                metadata = self.extract_metadata(filepath)
                if metadata and len(metadata) > 0:  # Only save if metadata found
                    # Add filename and source URL for reference
                    metadata['_FileName'] = os.path.basename(filepath)
                    # Find matching URL
                    for url in all_urls:
                        if os.path.basename(filepath).replace('_', '') in url:
                            metadata['_SourceURL'] = url
                            break
                    metadata_results.append(metadata)

            # Step 4: Save metadata to CSV
            if metadata_results:
                csv_file = os.path.join(self.output_dir, 'metadata.csv')
                
                # Get all field names
                fieldnames = set()
                for m in metadata_results:
                    fieldnames.update(m.keys())
                fieldnames = sorted(list(fieldnames))
                
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(metadata_results)
                
                print(f"\n[✓] Metadata saved to: {csv_file}")
                
                # Step 5: Show metadata analysis
                self.analyze_metadata(metadata_results)
                
                # Also save clean metadata-only JSON
                clean_metadata = []
                for m in metadata_results:
                    # Remove internal fields for clean JSON
                    clean = {k:v for k,v in m.items() if not k.startswith('_')}
                    clean_metadata.append(clean)
                
                with open(os.path.join(self.output_dir, 'metadata.json'), 'w') as f:
                    json.dump(clean_metadata, f, indent=2)
                
                print(f"\n[✓] Clean metadata JSON saved")
                
            else:
                print("\n[!] No metadata found in downloaded files")
        else:
            print("\n[!] No files downloaded")

        # API usage summary
        #print(f"\n[*] API Calls: {len(self.file_types)} of 1000 free monthly")
        print("[*] Done!")


def main():
    parser = argparse.ArgumentParser(description='Brave Meta Harvester - Metadata Focused')
    parser.add_argument('-d', '--domain', required=True, help='Target domain (eg. domain.com)')
    parser.add_argument('-k', '--api-key', required=True, help='Brave Search API key')
    parser.add_argument('-o', '--output', default='loot', help='Output directory')
    parser.add_argument('-m', '--max', type=int, default=100, help='Max files per type')
    parser.add_argument('-t', '--threads', type=int, default=5, help='Download threads')
    
    args = parser.parse_args()
    
    harvester = BraveMetaHarvester(
        domain=args.domain,
        api_key=args.api_key,
        output_dir=args.output,
        max_results=args.max,
        threads=args.threads
    )
    
    harvester.run()


if __name__ == '__main__':
    main()
