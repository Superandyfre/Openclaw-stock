"""
Helper utilities for OpenClaw Trading System
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
import numpy as np


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values
    
    Args:
        old_value: Original value
        new_value: New value
    
    Returns:
        Percentage change
    """
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100


def format_currency(value: float, currency: str = "USD") -> str:
    """
    Format value as currency
    
    Args:
        value: Numeric value
        currency: Currency code
    
    Returns:
        Formatted currency string
    """
    symbols = {
        "USD": "$",
        "KRW": "₩",
        "EUR": "€",
        "GBP": "£"
    }
    symbol = symbols.get(currency, currency)
    return f"{symbol}{value:,.2f}"


def calculate_volatility(prices: List[float], window: int = 20) -> float:
    """
    Calculate historical volatility
    
    Args:
        prices: List of historical prices
        window: Rolling window size
    
    Returns:
        Volatility value
    """
    if len(prices) < window:
        return 0.0
    
    returns = np.diff(np.log(prices[-window:]))
    return np.std(returns) * np.sqrt(252)  # Annualized


def is_trading_hours(market: str = "US") -> bool:
    """
    Check if current time is within trading hours
    
    Args:
        market: Market identifier (US, KR, CRYPTO)
    
    Returns:
        True if within trading hours
    """
    now = datetime.now()
    
    if market == "CRYPTO":
        return True  # Crypto trades 24/7
    
    # Simplified check - should use market-specific timezone
    if market == "US":
        # US market: 9:30 AM - 4:00 PM EST (Mon-Fri)
        if now.weekday() >= 5:  # Weekend
            return False
        return 9 <= now.hour < 16
    
    if market == "KR":
        # Korean market: 9:00 AM - 3:30 PM KST (Mon-Fri)
        if now.weekday() >= 5:  # Weekend
            return False
        return 9 <= now.hour < 15 or (now.hour == 15 and now.minute < 30)
    
    return False


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks
    
    Args:
        lst: Input list
        chunk_size: Size of each chunk
    
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def moving_average(data: List[float], window: int) -> List[float]:
    """
    Calculate simple moving average
    
    Args:
        data: Input data
        window: Window size
    
    Returns:
        Moving average values
    """
    if len(data) < window:
        return []
    
    result = []
    for i in range(len(data) - window + 1):
        result.append(sum(data[i:i + window]) / window)
    return result
