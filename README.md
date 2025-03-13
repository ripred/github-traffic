# github-traffic
command line utility to gather, organize, and display the metrics about all of your github repositories.
## Usage
```bash
usage: traffic.py [-h] [-e] [-z] [-c] [-s {views_total,views_unique,clones_total,clones_unique,stars,forks,combined_metrics}] [-t TIMEFRAME]

GitHub Repository Traffic Analyzer

options:
  -h, --help            show this help message and exit
  -e, --hide-empty      Hide repositories with all metrics equal to zero
  -z, --no-zero-views   Exclude repositories with zero views from the output
  -c, --write-csv       Write results to a CSV file
  -s {views_total,views_unique,clones_total,clones_unique,stars,forks,combined_metrics}, --sort-by {views_total,views_unique,clones_total,clones_unique,stars,forks,combined_metrics}
                        Sort results by a specific metric (default: combined_metrics)
  -t TIMEFRAME, --timeframe TIMEFRAME
                        Set the timeframe for reports in days (default: 14, GitHub API maximum)

Examples:
  python traffic.py                       # Basic usage with default settings
  python traffic.py -z                    # Exclude repos with zero views
  python traffic.py -e -c                 # Hide empty repos and save to CSV
  python traffic.py -s views_total        # Sort by total views
  python traffic.py -z -s clones_unique   # Show only repos with views, sorted by unique clones
  python traffic.py -t 14                 # Get data for the last 14 days (GitHub API maximum)
```
## Example Command Line Execution and Output ![](Screen%20Shot%202025-03-13%20at%201.00.52%20PM.png)
