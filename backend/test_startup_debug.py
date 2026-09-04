#!/usr/bin/env python3
"""Debug script to find where backend startup hangs."""
import sys
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, '.')

def test_imports():
    """Test basic imports."""
    logger.info("="*60)
    logger.info("TEST 1: Testing imports...")
    logger.info("="*60)

    try:
        logger.info("Importing app.core.config...")
        from app.core.config import settings
        logger.info("✓ settings imported")

        logger.info("Importing app.core.database...")
        from app.core.database import engine, SessionLocal
        logger.info("✓ database imported")

        logger.info("Importing app.models.base...")
        from app.models.base import Base
        logger.info("✓ models imported")

        return True
    except Exception as e:
        logger.error(f"✗ Import failed: {e}", exc_info=True)
        return False

def test_settings_validation():
    """Test settings validation."""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Validating settings...")
    logger.info("="*60)

    try:
        from app.core.config import settings
        logger.info("Calling settings.validate_config()...")
        start = time.time()
        settings.validate_config()
        elapsed = time.time() - start
        logger.info(f"✓ Settings validated in {elapsed:.2f}s")
        return True
    except Exception as e:
        logger.error(f"✗ Settings validation failed: {e}", exc_info=True)
        return False

def test_scheduler():
    """Test APScheduler startup."""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Starting APScheduler...")
    logger.info("="*60)

    try:
        from app.core.scheduler import start_scheduler
        logger.info("Calling start_scheduler()...")
        start = time.time()
        start_scheduler()
        elapsed = time.time() - start
        logger.info(f"✓ Scheduler started in {elapsed:.2f}s")
        return True
    except Exception as e:
        logger.error(f"✗ Scheduler startup failed: {e}", exc_info=True)
        return False

def test_database_tables():
    """Test database table creation."""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Creating database tables...")
    logger.info("="*60)

    try:
        from app.core.database import engine
        from app.models.base import Base

        logger.info("Calling Base.metadata.create_all()...")
        start = time.time()
        Base.metadata.create_all(bind=engine, checkfirst=True)
        elapsed = time.time() - start
        logger.info(f"✓ Tables created in {elapsed:.2f}s")
        return True
    except Exception as e:
        logger.error(f"✗ Table creation failed: {e}", exc_info=True)
        return False

def test_db_contract():
    """Test database contract initialization."""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Initializing database contract...")
    logger.info("="*60)

    try:
        from app.core.db_contract import initialize_database
        logger.info("Calling initialize_database()...")
        start = time.time()
        initialize_database()
        elapsed = time.time() - start
        logger.info(f"✓ Database contract initialized in {elapsed:.2f}s")
        return True
    except Exception as e:
        logger.error(f"✗ Database contract initialization failed: {e}", exc_info=True)
        return False

def test_org_positions():
    """Test organizational positions initialization."""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Initializing organizational positions...")
    logger.info("="*60)

    try:
        from app.core.database import SessionLocal
        from app.services.org_structure_service import init_default_positions

        logger.info("Creating database session...")
        db = SessionLocal()

        logger.info("Calling init_default_positions()...")
        start = time.time()
        result = init_default_positions(db)
        elapsed = time.time() - start

        db.close()
        logger.info(f"✓ Organizational positions initialized in {elapsed:.2f}s")
        logger.info(f"  Result: {result}")
        return True
    except Exception as e:
        logger.error(f"✗ Organizational positions initialization failed: {e}", exc_info=True)
        return False

def main():
    """Run all startup tests sequentially."""
    from threading import Thread
    import threading

    logger.info("BACKEND STARTUP DEBUG - Testing each component")
    logger.info("This will identify which startup step is hanging\n")

    tests = [
        ("Imports", test_imports),
        ("Settings Validation", test_settings_validation),
        ("Scheduler", test_scheduler),
        ("Database Tables", test_database_tables),
        ("Database Contract", test_db_contract),
        ("Organizational Positions", test_org_positions),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\nRunning: {test_name}")
        result_holder = [None]
        exception_holder = [None]

        def test_wrapper():
            try:
                result_holder[0] = test_func()
            except Exception as e:
                exception_holder[0] = e

        thread = Thread(target=test_wrapper, daemon=True)
        thread.start()
        thread.join(timeout=10)  # Wait max 10 seconds

        if thread.is_alive():
            # Thread is still running - it hung
            logger.error(f"✗ TIMEOUT: {test_name} - Test did not complete in 10 seconds\n")
            results.append((test_name, False))
        elif exception_holder[0]:
            logger.error(f"✗ ERROR: {test_name} - {exception_holder[0]}\n")
            results.append((test_name, False))
        else:
            result = result_holder[0]
            results.append((test_name, result))
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{status}: {test_name}\n")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    for test_name, result in results:
        status = "✓" if result else "✗"
        logger.info(f"{status} {test_name}")

    # Find first failure
    for test_name, result in results:
        if not result:
            logger.info(f"\n⚠️  BLOCKER: '{test_name}' is failing or hanging")
            logger.info("Fix this test before proceeding to the next one")
            break
    else:
        logger.info("\n✓ All startup tests passed!")

if __name__ == "__main__":
    main()
