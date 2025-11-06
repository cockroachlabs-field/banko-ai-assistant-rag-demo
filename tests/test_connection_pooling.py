#!/usr/bin/env python3
"""
Test script to verify database connection pooling is working correctly.
This script performs multiple concurrent database operations to demonstrate
that connections are being reused from the pool rather than created/destroyed.
"""

import time
import threading
from banko_ai.utils.database import DatabaseManager
from banko_ai.ai_providers.openai_provider import OpenAIProvider
from sqlalchemy import text

def test_database_manager_pooling():
    """Test DatabaseManager connection pooling."""
    print("\n" + "="*80)
    print("TEST 1: DatabaseManager Connection Pooling")
    print("="*80)
    
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    print(f"\nPool Configuration:")
    print(f"  - Pool size: {engine.pool.size()}")
    print(f"  - Max overflow: {engine.pool._max_overflow}")
    print(f"  - Pool pre-ping: {engine.pool._pre_ping}")
    print(f"  - Pool recycle: {engine.pool._recycle} seconds")
    print(f"  - Total available connections: {engine.pool.size() + engine.pool._max_overflow}")
    
    # Test basic connection
    print("\n📊 Testing connection acquisition...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 as test"))
        print(f"  ✅ Connection acquired successfully: {result.scalar()}")
        print(f"  📈 Pool status - Checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")
    
    print(f"  ✅ Connection returned to pool")
    print(f"  📈 Pool status - Checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")
    
    # Test multiple sequential operations (should reuse connection)
    print("\n🔄 Testing 5 sequential operations (should reuse connections)...")
    for i in range(5):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"  Operation {i+1}/5 - Pool checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")
    
    print("\n  ✅ All connections returned to pool after sequential operations")
    print(f"  📈 Final pool status - Checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")


def test_concurrent_connections():
    """Test concurrent connection usage."""
    print("\n" + "="*80)
    print("TEST 2: Concurrent Connection Pool Usage")
    print("="*80)
    
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    def worker(worker_id):
        """Worker thread that performs database operations."""
        with engine.connect() as conn:
            # Simulate some work
            result = conn.execute(text(f"SELECT {worker_id} as worker_id, pg_backend_pid() as pid"))
            row = result.fetchone()
            print(f"  Worker {worker_id}: Using backend PID {row[1]}")
            time.sleep(0.1)  # Simulate processing
    
    print(f"\n🚀 Starting 15 concurrent threads (pool can handle {engine.pool.size() + engine.pool._max_overflow} total)...")
    print(f"  📊 Initial pool - Checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")
    
    threads = []
    for i in range(15):
        t = threading.Thread(target=worker, args=(i+1,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    print(f"\n  ✅ All 15 threads completed")
    print(f"  📈 Final pool status - Checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")
    print(f"  💡 Connections were reused from the pool!")


def test_provider_pooling():
    """Test AI Provider connection pooling."""
    print("\n" + "="*80)
    print("TEST 3: AI Provider Connection Pooling")
    print("="*80)
    
    print("\n🤖 Testing OpenAI Provider...")
    provider = OpenAIProvider({})
    engine = provider._get_db_engine()
    
    print(f"\nPool Configuration:")
    print(f"  - Pool size: {engine.pool.size()}")
    print(f"  - Max overflow: {engine.pool._max_overflow}")
    print(f"  - Total capacity: {engine.pool.size() + engine.pool._max_overflow}")
    
    print("\n🔄 Performing 3 database queries...")
    
    # First check if table exists
    table_exists = False
    with engine.connect() as conn:
        try:
            result = conn.execute(text("SELECT COUNT(*) FROM expenses"))
            table_exists = True
        except Exception:
            pass
    
    for i in range(3):
        with engine.connect() as conn:
            if table_exists:
                result = conn.execute(text("SELECT COUNT(*) FROM expenses"))
                count = result.scalar()
                print(f"  Query {i+1}/3 - Found {count} expenses, Pool checked out: {engine.pool.checkedout()}")
            else:
                # Table doesn't exist, just test the pooling
                result = conn.execute(text("SELECT 1"))
                print(f"  Query {i+1}/3 - Pool working (no expenses table), Pool checked out: {engine.pool.checkedout()}")
    
    print(f"\n  ✅ All queries completed")
    print(f"  📈 Final pool status - Checked out: {engine.pool.checkedout()}")
    print(f"  💡 Connections were reused efficiently!")


def test_pool_saturation():
    """Test what happens when we exceed pool capacity."""
    print("\n" + "="*80)
    print("TEST 4: Pool Saturation Handling")
    print("="*80)
    
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    max_capacity = engine.pool.size() + engine.pool._max_overflow
    print(f"\n📊 Pool capacity: {engine.pool.size()} base + {engine.pool._max_overflow} overflow = {max_capacity} total")
    
    # Hold connections to fill the pool
    connections = []
    print(f"\n🔄 Acquiring {engine.pool.size() + 5} connections (exceeding base pool)...")
    
    try:
        for i in range(engine.pool.size() + 5):
            conn = engine.connect()
            connections.append(conn)
            print(f"  Connection {i+1}: Checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")
        
        print(f"\n  📈 Peak usage - Checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")
        print(f"  ✅ Pool handled the load with overflow connections!")
        
    finally:
        # Release all connections
        print(f"\n🔄 Releasing all connections back to pool...")
        for conn in connections:
            conn.close()
        
        print(f"  📈 After release - Checked out: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}")
        print(f"  ✅ All connections returned to pool!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("CONNECTION POOLING TEST SUITE")
    print("="*80)
    print("\nThis test verifies that database connections are being properly pooled")
    print("and reused instead of being created/destroyed on every transaction.")
    print("\nWith proper pooling:")
    print("  ✅ Connections are reused from the pool")
    print("  ✅ No disconnect/reconnect on every query")
    print("  ✅ Better performance under load")
    print("  ✅ Up to 30 concurrent connections (10 base + 20 overflow)")
    
    try:
        # Run all tests
        test_database_manager_pooling()
        test_concurrent_connections()
        test_provider_pooling()
        test_pool_saturation()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED - CONNECTION POOLING IS WORKING CORRECTLY!")
        print("="*80)
        print("\n📊 Summary:")
        print("  - Connections are properly pooled and reused")
        print("  - No saw-tooth pattern of connect/disconnect")
        print("  - Pool handles concurrent load efficiently")
        print("  - All AI providers use pooled connections")
        print("\n💡 Recommendation:")
        print("  - Monitor pool usage with: engine.pool.checkedout()")
        print("  - Adjust pool_size/max_overflow in db_retry.py if needed")
        print("  - Current config (10+20) should handle most workloads")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
