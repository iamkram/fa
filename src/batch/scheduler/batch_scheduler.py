"""
Batch Scheduler - Triggers nightly batch processing at 2 AM

This script runs continuously and executes the batch assistant graph
at 2 AM local time daily using APScheduler.

Usage:
    python3 src/batch/scheduler/batch_scheduler.py

To run as a background service:
    nohup python3 src/batch/scheduler/batch_scheduler.py > logs/scheduler.log 2>&1 &
"""

import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import signal
import sys

from src.batch.graphs.batch_assistant_graph import batch_assistant_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/batch_scheduler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BatchScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    async def run_batch_job(self):
        """Execute the batch assistant graph"""
        try:
            logger.info("🌙 Nightly batch job triggered at 2 AM")
            logger.info(f"⏰ Current time: {datetime.now().isoformat()}")

            # Initialize state for the batch run
            initial_state = {
                "trigger_time": datetime.now().isoformat(),
                "stocks_to_process": [],
                "processed_count": 0,
                "failed_count": 0,
                "batch_run_id": "",
                "status": "INITIALIZING",
                "error_message": None
            }

            # Invoke the batch assistant graph
            logger.info("🚀 Starting batch assistant graph execution")
            result = await batch_assistant_graph.ainvoke(initial_state)

            # Log results
            logger.info(f"✅ Batch job completed with status: {result['status']}")
            logger.info(f"📊 Processed: {result['processed_count']}, Failed: {result['failed_count']}")

            if result.get('error_message'):
                logger.error(f"❌ Batch job error: {result['error_message']}")

        except Exception as e:
            logger.error(f"❌ Critical error in batch job execution: {e}", exc_info=True)

    def start(self):
        """Start the scheduler"""
        # Schedule the batch job for 2 AM daily
        # Cron format: minute hour day month day_of_week
        self.scheduler.add_job(
            self.run_batch_job,
            trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM daily
            id='nightly_batch_job',
            name='Nightly Stock Summary Batch Processing',
            replace_existing=True
        )

        logger.info("⏰ Batch scheduler initialized")
        logger.info("📅 Schedule: Daily at 2:00 AM local time")
        logger.info(f"🕐 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Calculate next run time
        next_run = self.scheduler.get_job('nightly_batch_job').next_run_time
        logger.info(f"⏭️  Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

        self.scheduler.start()
        self.is_running = True

        logger.info("✅ Scheduler started successfully")

    def stop(self):
        """Stop the scheduler"""
        if self.is_running:
            logger.info("🛑 Stopping batch scheduler...")
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("✅ Scheduler stopped")

async def main():
    """Main entry point"""
    scheduler = BatchScheduler()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"\n⚠️  Received signal {sig}, shutting down gracefully...")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the scheduler
    scheduler.start()

    logger.info("🔄 Scheduler is running. Press Ctrl+C to stop.")

    # Keep the event loop running
    try:
        while scheduler.is_running:
            await asyncio.sleep(60)  # Sleep for 1 minute intervals
    except KeyboardInterrupt:
        logger.info("\n⚠️  Keyboard interrupt received")
        scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
