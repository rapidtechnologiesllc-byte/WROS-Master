"""
Queue Monitoring & Statistics Script
=====================================

Real-time monitoring of message queue status during test execution.
Provides continuous visibility into task progress and queue health.

Usage:
    python scripts/monitor_queue.py [--interval 5] [--duration 600]

Arguments:
    --interval: Update interval in seconds (default: 5)
    --duration: Total monitoring duration in seconds (default: 600)
"""

import sys
import os
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.endpoints.admin_queue import TaskStatus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def format_time_remaining(seconds: int) -> str:
    """Format seconds into readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"

def print_status_bar(current: int, total: int, width: int = 40) -> str:
    """Generate a text-based progress bar."""
    if total == 0:
        return "[" + "=" * width + "]"

    filled = int((current / total) * width)
    empty = width - filled
    percentage = (current / total) * 100

    bar = "[" + "=" * filled + " " * empty + "]"
    return f"{bar} {percentage:.1f}%"

def get_queue_stats() -> Dict:
    """Get current queue statistics."""
    all_tasks = TaskStatus.get_all_tasks()

    stats = {
        "timestamp": datetime.utcnow(),
        "total": len(all_tasks),
        "queued": len([t for t in all_tasks if t["status"] == "queued"]),
        "active": len([t for t in all_tasks if t["status"] == "active"]),
        "completed": len([t for t in all_tasks if t["status"] == "completed"]),
        "failed": len([t for t in all_tasks if t["status"] == "failed"]),
    }

    return stats

def calculate_throughput(prev_stats: Dict, curr_stats: Dict, elapsed: float) -> Dict:
    """Calculate throughput metrics."""
    if elapsed == 0:
        return {}

    completed_delta = curr_stats.get("completed", 0) - prev_stats.get("completed", 0)
    failed_delta = curr_stats.get("failed", 0) - prev_stats.get("failed", 0)

    return {
        "tasks_per_second": completed_delta / elapsed if elapsed > 0 else 0,
        "completed_rate": f"{completed_delta} tasks in {elapsed:.1f}s",
    }

def monitor_queue(interval: int = 5, duration: int = 600):
    """Monitor queue status at regular intervals."""

    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}")
    print(f"MESSAGE QUEUE REAL-TIME MONITOR")
    print(f"{'='*80}{Colors.END}\n")

    print(f"Monitoring Parameters:")
    print(f"  Update Interval: {interval} seconds")
    print(f"  Duration: {duration} seconds (~{duration/60:.1f} minutes)")
    print(f"  Start Time: {datetime.utcnow().strftime('%H:%M:%S')}")
    print(f"  Est. End Time: {(datetime.utcnow() + timedelta(seconds=duration)).strftime('%H:%M:%S')}")
    print(f"\nPress Ctrl+C to stop monitoring\n")

    start_time = datetime.utcnow()
    prev_stats = None
    update_count = 0

    try:
        while True:
            elapsed_total = (datetime.utcnow() - start_time).total_seconds()

            # Check if duration exceeded
            if elapsed_total >= duration:
                print(f"\n{Colors.YELLOW}Monitoring duration reached. Stopping.{Colors.END}")
                break

            # Get current stats
            curr_stats = get_queue_stats()
            update_count += 1

            # Clear previous output (works on Windows and Unix)
            os.system('cls' if os.name == 'nt' else 'clear')

            # Print header
            print(f"{Colors.HEADER}{Colors.BOLD}MESSAGE QUEUE MONITOR{Colors.END}")
            print(f"Update #{update_count} | {datetime.utcnow().strftime('%H:%M:%S')} | "
                  f"Elapsed: {format_time_remaining(int(elapsed_total))}\n")

            # Print stats
            print(f"{Colors.BOLD}Queue Status:{Colors.END}")
            print(f"  Total Tasks:    {curr_stats['total']:4d}")
            print(f"  Queued:         {Colors.YELLOW}{curr_stats['queued']:4d}{Colors.END}")
            print(f"  Active:         {Colors.CYAN}{curr_stats['active']:4d}{Colors.END}")
            print(f"  Completed:      {Colors.GREEN}{curr_stats['completed']:4d}{Colors.END}")
            print(f"  Failed:         {Colors.RED}{curr_stats['failed']:4d}{Colors.END}")

            # Print progress bars
            print(f"\n{Colors.BOLD}Progress:{Colors.END}")
            if curr_stats['total'] > 0:
                completed_bar = print_status_bar(curr_stats['completed'], curr_stats['total'])
                print(f"  Completed: {completed_bar}")

                queued_bar = print_status_bar(curr_stats['queued'], curr_stats['total'])
                print(f"  Queued:    {queued_bar}")

            # Calculate and print throughput
            if prev_stats and prev_stats.get('timestamp'):
                elapsed_since_last = (
                    curr_stats['timestamp'] - prev_stats['timestamp']
                ).total_seconds()

                throughput = calculate_throughput(prev_stats, curr_stats, elapsed_since_last)
                if throughput.get('tasks_per_second'):
                    print(f"\n{Colors.BOLD}Throughput:{Colors.END}")
                    print(f"  Rate: {throughput['tasks_per_second']:.2f} tasks/second")
                    print(f"  Status: {throughput['completed_rate']}")

            # Estimate completion time
            if curr_stats['completed'] > 0 and curr_stats['queued'] > 0:
                total_tasks = curr_stats['total']
                completed = curr_stats['completed']
                avg_time = elapsed_total / completed if completed > 0 else 0
                remaining_tasks = curr_stats['queued'] + curr_stats['active']
                est_remaining = avg_time * remaining_tasks

                print(f"\n{Colors.BOLD}Estimate:{Colors.END}")
                print(f"  Avg Time per Task: {avg_time:.2f} seconds")
                print(f"  Est. Remaining Time: {format_time_remaining(int(est_remaining))}")
                print(f"  Est. Total Time: {format_time_remaining(int(elapsed_total + est_remaining))}")

            # Print error summary if any failed
            if curr_stats['failed'] > 0:
                print(f"\n{Colors.RED}{Colors.BOLD}⚠️  ATTENTION: {curr_stats['failed']} task(s) failed!{Colors.END}")
                all_tasks = TaskStatus.get_all_tasks()
                failed_tasks = [t for t in all_tasks if t["status"] == "failed"][:5]

                if failed_tasks:
                    print(f"  Recent failures (showing first 5):")
                    for task in failed_tasks:
                        print(f"    - {task['task_id']}: {task.get('task_name', 'unknown')}")

            # Ready for next update
            prev_stats = curr_stats
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Monitoring stopped by user{Colors.END}")

    # Final summary
    final_stats = get_queue_stats()
    total_elapsed = (datetime.utcnow() - start_time).total_seconds()

    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}")
    print(f"MONITORING SESSION SUMMARY")
    print(f"{'='*80}{Colors.END}\n")

    print(f"Session Statistics:")
    print(f"  Total Duration: {format_time_remaining(int(total_elapsed))}")
    print(f"  Updates: {update_count}")
    print(f"  Update Interval: {interval}s")

    print(f"\nFinal Queue State:")
    print(f"  Total Tasks:    {final_stats['total']}")
    print(f"  Queued:         {final_stats['queued']}")
    print(f"  Active:         {final_stats['active']}")
    print(f"  Completed:      {final_stats['completed']}")
    print(f"  Failed:         {final_stats['failed']}")

    if final_stats['completed'] > 0:
        avg_time = total_elapsed / final_stats['completed']
        print(f"\nPerformance:")
        print(f"  Avg Time per Task: {avg_time:.2f} seconds")
        print(f"  Tasks per Second: {final_stats['completed'] / total_elapsed:.2f}")
        print(f"  Success Rate: {(final_stats['completed'] / final_stats['total'] * 100):.1f}%")

    print(f"\n{'='*80}\n")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor message queue status in real-time"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Update interval in seconds (default: 5)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=600,
        help="Monitoring duration in seconds (default: 600)"
    )

    args = parser.parse_args()

    monitor_queue(interval=args.interval, duration=args.duration)

if __name__ == "__main__":
    main()
