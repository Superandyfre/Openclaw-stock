"""
Scheduler for OpenClaw Trading System
"""
import asyncio
from typing import Callable, Dict, Any, Optional
from datetime import datetime
from loguru import logger


class Scheduler:
    """Task scheduler for periodic and one-time tasks"""
    
    def __init__(self):
        """Initialize scheduler"""
        self.tasks: Dict[str, asyncio.Task] = {}
        self.running = False
    
    async def schedule_periodic(
        self,
        name: str,
        func: Callable,
        interval: int,
        *args,
        **kwargs
    ):
        """
        Schedule a periodic task
        
        Args:
            name: Task name
            func: Async function to execute
            interval: Interval in seconds
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        """
        async def periodic_wrapper():
            while self.running:
                try:
                    start_time = datetime.now()
                    
                    if asyncio.iscoroutinefunction(func):
                        await func(*args, **kwargs)
                    else:
                        func(*args, **kwargs)
                    
                    elapsed = (datetime.now() - start_time).total_seconds()
                    
                    # Wait for remaining interval time
                    wait_time = max(0, interval - elapsed)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(
                            f"Task '{name}' took {elapsed:.2f}s, "
                            f"longer than interval {interval}s"
                        )
                except asyncio.CancelledError:
                    logger.info(f"Task '{name}' cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in task '{name}': {e}")
                    await asyncio.sleep(interval)
        
        if name in self.tasks:
            logger.warning(f"Task '{name}' already scheduled, cancelling old task")
            self.cancel_task(name)
        
        self.tasks[name] = asyncio.create_task(periodic_wrapper())
        logger.info(f"Scheduled periodic task '{name}' with interval {interval}s")
    
    async def schedule_once(
        self,
        name: str,
        func: Callable,
        delay: int,
        *args,
        **kwargs
    ):
        """
        Schedule a one-time task
        
        Args:
            name: Task name
            func: Async function to execute
            delay: Delay in seconds before execution
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        """
        async def once_wrapper():
            try:
                await asyncio.sleep(delay)
                
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
                
                # Remove from tasks dict after completion
                self.tasks.pop(name, None)
            except asyncio.CancelledError:
                logger.info(f"One-time task '{name}' cancelled")
            except Exception as e:
                logger.error(f"Error in one-time task '{name}': {e}")
        
        if name in self.tasks:
            logger.warning(f"Task '{name}' already scheduled, cancelling old task")
            self.cancel_task(name)
        
        self.tasks[name] = asyncio.create_task(once_wrapper())
        logger.info(f"Scheduled one-time task '{name}' with delay {delay}s")
    
    def cancel_task(self, name: str) -> bool:
        """
        Cancel a scheduled task
        
        Args:
            name: Task name
        
        Returns:
            True if task was cancelled
        """
        if name in self.tasks:
            self.tasks[name].cancel()
            del self.tasks[name]
            logger.info(f"Cancelled task '{name}'")
            return True
        return False
    
    def start(self):
        """Start the scheduler"""
        self.running = True
        logger.info("Scheduler started")
    
    async def stop(self):
        """Stop the scheduler and cancel all tasks"""
        self.running = False
        
        for name, task in list(self.tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.tasks.clear()
        logger.info("Scheduler stopped, all tasks cancelled")
    
    def get_task_status(self) -> Dict[str, str]:
        """
        Get status of all tasks
        
        Returns:
            Dict mapping task names to their status
        """
        status = {}
        for name, task in self.tasks.items():
            if task.done():
                status[name] = "completed"
            elif task.cancelled():
                status[name] = "cancelled"
            else:
                status[name] = "running"
        return status
