#!/usr/bin/env python3
"""
Format for credentials.ini:

[github]
username = USERNAME
token = REDDIT_APP_SECRET_TOKEN
"""

import requests
import pandas as pd
import configparser
import os
import argparse
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ANSI escape codes for terminal colors with better contrast
class Colors:
    # High contrast colors for better visibility
    GREEN = '\033[1;32m'  # Bright green text
    RED = '\033[1;31m'    # Bright red text
    YELLOW = '\033[1;33m' # Bright yellow text
    BLUE = '\033[1;34m'   # Bright blue text
    MAGENTA = '\033[1;35m' # Bright magenta text
    CYAN = '\033[1;36m'   # Bright cyan text
    WHITE = '\033[1;37m'  # Bright white text
    GRAY = '\033[0;37m'   # Gray text
    RESET = '\033[0m'     # Reset to default

def fetch_repo_traffic(repo, i, total_repos, username, token, result_queue, timeframe=None):
    """Fetch traffic data for a single repository"""
    repo_name = repo['name']
    
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # GitHub API only provides traffic data for the last 14 days
    views_url = f'https://api.github.com/repos/{username}/{repo_name}/traffic/views'
    clones_url = f'https://api.github.com/repos/{username}/{repo_name}/traffic/clones'
    
    views_response = requests.get(views_url, headers=headers)
    clones_response = requests.get(clones_url, headers=headers)
    
    # Get data from responses, silently handle errors
    if views_response.status_code != 200:
        views = {"count": 0, "uniques": 0}
    else:
        views = views_response.json()
        
    if clones_response.status_code != 200:
        clones = {"count": 0, "uniques": 0}
    else:
        clones = clones_response.json()
    
    # Extract traffic stats
    views_total = views.get('count', 0)
    views_unique = views.get('uniques', 0)
    clones_total = clones.get('count', 0)
    clones_unique = clones.get('uniques', 0)
    stars = repo['stargazers_count']
    forks = repo['forks_count']
    
    # Get date range information
    views_timerange = None
    if 'views' in views and views['views']:
        first_date = views['views'][0]['timestamp'].split('T')[0]
        last_date = views['views'][-1]['timestamp'].split('T')[0]
        views_timerange = f"{first_date} to {last_date}"
    
    # Status indicators
    views_status = "✅" if views_response.status_code == 200 else "❌"
    clones_status = "✅" if clones_response.status_code == 200 else "❌"
    
    # Print progress with thread-safe approach
    with print_lock:
        print(f"\r[{i}/{total_repos}] {repo_name} | Views: {views_total}/{views_unique} {views_status} | Clones: {clones_total}/{clones_unique} {clones_status} | Stars: {stars} | Forks: {forks}\033[K", end="")
    
    # Add result to queue
    result_queue.put({
        'repository': repo_name,
        'views_total': views_total,
        'views_unique': views_unique,
        'clones_total': clones_total,
        'clones_unique': clones_unique,
        'stars': stars,
        'forks': forks,
        'date_range': views_timerange
    })

# Create a lock for thread-safe printing
print_lock = threading.Lock()

def get_repo_traffic(username, token, timeframe=None):
    print(f"Starting GitHub traffic analysis for user: {username}")
    if timeframe:
        print(f"Using timeframe of {timeframe} days")
    
    # Get all repositories for the user
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Check token validity and permissions
    rate_limit_url = 'https://api.github.com/rate_limit'
    rate_response = requests.get(rate_limit_url, headers=headers)
    
    if rate_response.status_code != 200:
        print(f"Error: Authentication failed. Status code: {rate_response.status_code}")
        print("Please check that your token is valid.")
        exit(1)
    
    # Get repositories
    repos_url = f'https://api.github.com/users/{username}/repos?per_page=1000'
    response = requests.get(repos_url, headers=headers)
    repos = response.json()
    
    print(f"Found {len(repos)} repositories to examine")
    
    # Issue warning about permissions if needed
    test_repo = repos[0]['name'] if repos else None
    if test_repo:
        test_url = f'https://api.github.com/repos/{username}/{test_repo}/traffic/views'
        test_response = requests.get(test_url, headers=headers)
        if test_response.status_code == 403:
            print("\nWARNING: Your token doesn't have permission to access traffic data.")
            print("The script will continue but will only show stars and forks.")
            print("To access traffic data, generate a new token with the 'repo' scope.")
            print("See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token\n")
    
    # Create a queue for results
    result_queue = queue.Queue()
    
    # Process repositories in batches of 10 with ThreadPoolExecutor
    BATCH_SIZE = 10
    total_repos = len(repos)
    
    with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
        # Submit tasks for each repository
        futures = []
        for i, repo in enumerate(repos, 1):
            future = executor.submit(
                fetch_repo_traffic,
                repo, i, total_repos, username, token, result_queue, timeframe
            )
            futures.append(future)
    
    # Wait for all tasks to complete
    print("\nProcessing complete. Collecting results...")
    
    # Collect all results from the queue
    traffic_data = []
    while not result_queue.empty():
        traffic_data.append(result_queue.get())
    
    # Convert to DataFrame
    df = pd.DataFrame(traffic_data)
    
    # Add a combined_metrics column with weighted values for sorting
    # We'll weight stars and forks lower than views/clones to prioritize actual traffic
    df['combined_metrics'] = (
        (df['views_total'] * 1.0) + 
        (df['views_unique'] * 1.5) + 
        (df['clones_total'] * 2.0) + 
        (df['clones_unique'] * 3.0) + 
        (df['stars'] * 0.5) + 
        (df['forks'] * 1.0)
    )
    
    return df

# Read credentials from ini file
def read_credentials():
    config = configparser.ConfigParser()
    if os.path.exists('credentials.ini'):
        config.read('credentials.ini')
        if 'github' in config:
            return config['github']['username'], config['github']['token']
    
    print("Error: credentials.ini file not found or missing required data")
    exit(1)

# Main execution
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='GitHub Repository Traffic Analyzer',
        epilog='''
Examples:
  python traffic.py                       # Basic usage with default settings
  python traffic.py -z                    # Exclude repos with zero views
  python traffic.py -e -c                 # Hide empty repos and save to CSV
  python traffic.py -s views_total        # Sort by total views
  python traffic.py -z -s clones_unique   # Show only repos with views, sorted by unique clones
  python traffic.py -t 14                 # Get data for the last 14 days (GitHub API maximum)
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-e', '--hide-empty', action='store_true', 
                      help='Hide repositories with all metrics equal to zero')
    parser.add_argument('-z', '--no-zero-views', action='store_true',
                      help='Exclude repositories with zero views from the output')
    parser.add_argument('-c', '--write-csv', action='store_true',
                      help='Write results to a CSV file')
    parser.add_argument('-s', '--sort-by', type=str, choices=['views_total', 'views_unique', 'clones_total', 
                        'clones_unique', 'stars', 'forks', 'combined_metrics'],
                      default='combined_metrics',
                      help='Sort results by a specific metric (default: combined_metrics)')
    parser.add_argument('-t', '--timeframe', type=int, default=14,
                      help='Set the timeframe for reports in days (default: 14, GitHub API maximum)')
    args = parser.parse_args()
    
    username, token = read_credentials()
    
    # Set timeframe (maximum 14 days per GitHub API limitation)
    timeframe = min(args.timeframe, 14)  # Limit to 14 days
    if timeframe < args.timeframe:
        print(f"Note: GitHub API only provides traffic data for the last 14 days. Requested {args.timeframe} days, using maximum of 14 days.")
    
    # Get the traffic data
    traffic_df = get_repo_traffic(username, token, timeframe)
    
    # Sort by the specified column (descending so highest metrics are at top)
    traffic_df = traffic_df.sort_values(by=args.sort_by, ascending=False)
    
    # Filter out repos with all zeros if requested
    if args.hide_empty:
        traffic_df = traffic_df[traffic_df['combined_metrics'] > 0]
    
    # Filter out repos with zero views if requested
    if args.no_zero_views:
        traffic_df = traffic_df[traffic_df['views_total'] > 0]
    
    # Save to CSV only if --write-csv option is specified
    csv_filename = None
    if args.write_csv:
        csv_filename = f'github_traffic_{datetime.now().strftime("%Y%m%d")}.csv'
        # Save all data including date range in CSV 
        # (just remove combined_metrics column which is internal)
        traffic_df.drop('combined_metrics', axis=1).to_csv(csv_filename, index=False)
    
    # Print summary table with explanation
    # Get date range for all repositories
    date_ranges = [r for r in traffic_df['date_range'].dropna().unique() if r]
    date_range_str = ""
    if date_ranges:
        date_range_str = f" | Data period: {date_ranges[0]}"
    
    # Add timeframe info to the title
    timeframe_str = ""
    if args.timeframe != 14:  # Only if different from default
        timeframe_str = f" | Requested: {args.timeframe} days (limited to 14 days by GitHub API)"
    
    print(f"\n===== REPOSITORY TRAFFIC SUMMARY (Sorted by: {Colors.CYAN}{args.sort_by}{Colors.RESET}){Colors.MAGENTA}{date_range_str}{timeframe_str}{Colors.RESET} =====")
    
    # Check if we have any non-zero traffic data
    has_traffic_data = (traffic_df['views_total'].sum() > 0 or traffic_df['clones_total'].sum() > 0)
    
    if not has_traffic_data:
        print("\nNOTE: No view or clone data available. Sorting may be based on stars and forks only.")
        print("To get traffic data, you need a GitHub token with 'repo' scope permissions.\n")
    
    # Add numbering to repositories in all cases
    # Drop date_range column from display (it's already shown in the header)
    columns_to_drop = ['combined_metrics', 'date_range']
    
    # Filter if hide-empty is used
    traffic_df_display = traffic_df.copy()
    
    # Print with position numbering when sorting
    traffic_df_display = traffic_df_display.drop(columns=columns_to_drop, axis=1)
    
    # Add position column starting at 1 when sorting by a specific column
    if args.sort_by:
        traffic_df_display.insert(0, '#', range(1, len(traffic_df_display) + 1))
    
    # Apply colors to column headers
    color_map = {
        '#': Colors.WHITE,
        'repository': Colors.GREEN,
        'views_total': Colors.BLUE, 
        'views_unique': Colors.CYAN,
        'clones_total': Colors.YELLOW,
        'clones_unique': Colors.MAGENTA,
        'stars': Colors.RED,
        'forks': Colors.GRAY
    }
    
    # Format the DataFrame with colored headers
    pd.set_option('display.max_rows', None)
    formatted_df = traffic_df_display.copy()
    
    # Convert DataFrame to string representation
    df_string = formatted_df.to_string(index=False)
    
    # Find the header line and color each column name
    lines = df_string.split('\n')
    if len(lines) > 0:
        header = lines[0]
        colored_header = header
        
        # Color each column name
        for col, color in color_map.items():
            if col in header:
                colored_header = colored_header.replace(col, f"{color}{col}{Colors.RESET}")
        
        # Replace the header with colored version
        lines[0] = colored_header
        
        # Print the modified string representation
        print('\n'.join(lines))
    
    if csv_filename:
        print(f"\nTraffic data saved to {csv_filename}")
