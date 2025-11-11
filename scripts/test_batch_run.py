#!/usr/bin/env python3
"""
Test script to manually run the batch assistant graph
This allows testing before enabling the nightly scheduler
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.batch.graphs.batch_assistant_graph import batch_assistant_graph
from datetime import datetime


async def test_batch_run():
    """Run a test batch processing cycle"""

    print("=" * 60)
    print("BATCH ASSISTANT GRAPH - TEST RUN")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initial state for the batch assistant graph
    initial_state = {
        "trigger_time": datetime.now().isoformat(),
        "stocks_to_process": [],
        "processed_count": 0,
        "failed_count": 0,
        "batch_run_id": "",
        "status": "PENDING",
        "error_message": None,
        "messages": [],
        "initialized": False,
        "stocks_processed": False,
        "finalized": False,
        "next_agent": None
    }

    print("🚀 Invoking batch assistant graph...")
    print()

    try:
        # Run the graph
        result = await batch_assistant_graph.ainvoke(initial_state)

        print()
        print("=" * 60)
        print("BATCH RUN RESULTS")
        print("=" * 60)
        print(f"Batch Run ID: {result.get('batch_run_id', 'N/A')}")
        print(f"Status: {result.get('status', 'N/A')}")
        print(f"Stocks Processed: {result.get('processed_count', 0)}")
        print(f"Stocks Failed: {result.get('failed_count', 0)}")
        print(f"Total Stocks: {len(result.get('stocks_to_process', []))}")

        if result.get('error_message'):
            print(f"\n❌ Error: {result['error_message']}")

        print("\n📝 Execution Log:")
        for msg in result.get('messages', []):
            print(f"  {msg.content}")

        print()
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        return result

    except Exception as e:
        print(f"\n❌ Error running batch: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("\nTesting Batch Assistant Graph...")
    print("This will process ALL stocks in the database")
    print()

    result = asyncio.run(test_batch_run())

    if result and result.get('status') == 'COMPLETED':
        print("\n✅ Test batch run completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Test batch run failed!")
        sys.exit(1)
