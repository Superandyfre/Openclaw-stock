"""
OpenClaw Auto Trading System - Main Entry Point
"""
import asyncio
import sys
from pathlib import Path

# Add openclaw to path
sys.path.insert(0, str(Path(__file__).parent))

from openclaw.core.engine import OpenClawEngine
from openclaw.utils.logger import setup_logger


async def main():
    """Main application entry point"""
    logger = setup_logger()
    logger.info("🦞 Starting OpenClaw Auto Trading System")
    
    engine = OpenClawEngine()
    
    try:
        await engine.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("⏹️  Shutting down gracefully...")
        await engine.stop()
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        await engine.stop()
        raise


if __name__ == "__main__":
    asyncio.run(main())
