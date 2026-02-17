"""
Database manager for OpenClaw Trading System
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache")


class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        """
        Initialize database manager
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
        """
        self.redis_client: Optional[Any] = None
        self.memory_cache: Dict[str, Any] = {}
        
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    decode_responses=True
                )
                self.redis_client.ping()
                logger.info(f"✅ Connected to Redis at {redis_host}:{redis_port}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache.")
                self.redis_client = None
    
    def set(self, key: str, value: Any, expiry: Optional[int] = None) -> bool:
        """
        Set a key-value pair
        
        Args:
            key: Cache key
            value: Value to store
            expiry: Expiration time in seconds
        
        Returns:
            True if successful
        """
        try:
            serialized = json.dumps(value)
            
            if self.redis_client:
                if expiry:
                    self.redis_client.setex(key, expiry, serialized)
                else:
                    self.redis_client.set(key, serialized)
            else:
                self.memory_cache[key] = {
                    'value': serialized,
                    'expiry': datetime.now().timestamp() + expiry if expiry else None
                }
            return True
        except Exception as e:
            logger.error(f"Failed to set key {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value by key
        
        Args:
            key: Cache key
        
        Returns:
            Stored value or None
        """
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            else:
                cached = self.memory_cache.get(key)
                if cached:
                    if cached['expiry'] is None or cached['expiry'] > datetime.now().timestamp():
                        return json.loads(cached['value'])
                    else:
                        del self.memory_cache[key]
                return None
        except Exception as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """
        Delete a key
        
        Args:
            key: Cache key
        
        Returns:
            True if successful
        """
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                self.memory_cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {e}")
            return False
    
    def get_list(self, key: str) -> List[Any]:
        """
        Get list from cache
        
        Args:
            key: Cache key
        
        Returns:
            List of values
        """
        value = self.get(key)
        return value if isinstance(value, list) else []
    
    def append_to_list(self, key: str, value: Any, max_length: Optional[int] = None) -> bool:
        """
        Append value to a list
        
        Args:
            key: Cache key
            value: Value to append
            max_length: Maximum list length (oldest removed if exceeded)
        
        Returns:
            True if successful
        """
        try:
            current_list = self.get_list(key)
            current_list.append(value)
            
            if max_length and len(current_list) > max_length:
                current_list = current_list[-max_length:]
            
            return self.set(key, current_list)
        except Exception as e:
            logger.error(f"Failed to append to list {key}: {e}")
            return False
    
    def close(self):
        """Close database connections"""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Closed Redis connection")
