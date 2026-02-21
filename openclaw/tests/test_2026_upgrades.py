"""
Tests for 2026 OpenClaw upgrades
"""
import pytest
import asyncio
from datetime import datetime


class TestCurrencyConverter:
    """Test currency converter functionality"""
    
    @pytest.mark.asyncio
    async def test_currency_detection(self):
        """Test asset currency detection"""
        from openclaw.skills.utils.currency_converter import CurrencyConverter
        
        converter = CurrencyConverter()
        
        # Test Korean stocks
        assert converter.get_asset_currency("005930.KS") == "KRW"
        assert converter.get_asset_currency("000660.KQ") == "KRW"
        
        # Test US stocks
        assert converter.get_asset_currency("AAPL") == "USD"
        assert converter.get_asset_currency("TSLA") == "USD"
        
        # Test crypto
        assert converter.get_asset_currency("BTC-USD") == "USD"
        assert converter.get_asset_currency("KRW-BTC") == "KRW"
    
    @pytest.mark.asyncio
    async def test_krw_conversion(self):
        """Test KRW conversion with fallback rates"""
        from openclaw.skills.utils.currency_converter import CurrencyConverter
        
        converter = CurrencyConverter()
        await converter.update_rates()  # Will use fallback rates in test env
        
        # Test USD to KRW (using fallback rate 1335)
        krw_amount = await converter.convert_to_krw(100, "USD")
        assert krw_amount == 133500.0
        
        # Test KRW to KRW (no conversion)
        krw_amount = await converter.convert_to_krw(75000, "KRW")
        assert krw_amount == 75000.0
    
    def test_krw_formatting(self):
        """Test KRW amount formatting"""
        from openclaw.skills.utils.currency_converter import CurrencyConverter
        
        converter = CurrencyConverter()
        
        # Test formatting
        assert converter.format_krw(89445000) == "₩89,445,000"
        assert converter.format_krw(1234.56) == "₩1,235"
        assert converter.format_krw(75000) == "₩75,000"
    
    def test_percentage_formatting(self):
        """Test percentage formatting"""
        from openclaw.skills.utils.currency_converter import CurrencyConverter
        
        converter = CurrencyConverter()
        
        # Test percentage formatting
        assert converter.format_change(0.0235) == "+2.35%"
        assert converter.format_change(-0.0147) == "-1.47%"
        assert converter.format_change(0.05) == "+5.00%"
        assert converter.format_change(-0.02) == "-2.00%"


class TestAIModels:
    """Test AI models manager"""
    
    def test_ai_manager_initialization(self):
        """Test AI manager can be initialized"""
        from openclaw.skills.analysis.ai_models import AIModels
        
        # Should initialize without API keys for testing
        manager = AIModels()
        
        # Check basic properties
        assert hasattr(manager, 'models')
        assert hasattr(manager, 'model_stats')
        assert hasattr(manager, 'news_sources')
        assert hasattr(manager, 'asset_keywords')
    
    def test_model_routing_logic(self):
        """Test intelligent model routing (dual-model architecture)"""
        from openclaw.skills.analysis.ai_models import AIModels
        
        manager = AIModels()
        
        # Test routing for normal scenario (should always choose gemini)
        context = {
            'severity': 'low',
            'change_5m': 1.5,
            'anomaly_type': 'price_spike'
        }
        model = manager._choose_model(context, [])
        # Should choose gemini (or none if no clients available in test)
        assert model in ['gemini', 'deepseek', 'none']
        
        # Test routing for critical scenario (still gemini in dual-model)
        context = {
            'severity': 'critical',
            'change_5m': 7.5,
            'anomaly_type': 'flash_crash'
        }
        model = manager._choose_model(context, [])
        # Should still prefer gemini in dual-model architecture
        assert model in ['gemini', 'deepseek', 'none']
    
    def test_news_deduplication(self):
        """Test news deduplication"""
        from openclaw.skills.analysis.ai_models import AIModels
        
        manager = AIModels()
        
        # Create duplicate news
        news = [
            {'title': 'Bitcoin Reaches New High', 'source': 'A'},
            {'title': 'Bitcoin reaches new high', 'source': 'B'},  # Duplicate
            {'title': 'Ethereum Updates Coming', 'source': 'C'},
        ]
        
        unique = manager._deduplicate_news(news)
        assert len(unique) == 2  # Should remove one duplicate
    
    def test_news_relevance_scoring(self):
        """Test news relevance scoring"""
        from openclaw.skills.analysis.ai_models import AIModels
        
        manager = AIModels()
        
        news = [
            {
                'title': 'Bitcoin price surge',
                'description': 'Bitcoin reaches new high',
                'published_date': datetime.now()
            }
        ]
        
        keywords = ['bitcoin', 'btc']
        scored = manager._score_news_relevance(news, keywords)
        
        assert 'relevance_score' in scored[0]
        assert scored[0]['relevance_score'] > 0
    
    def test_model_statistics(self):
        """Test model usage statistics (dual-model architecture)"""
        from openclaw.skills.analysis.ai_models import AIModels
        
        manager = AIModels()
        
        stats = manager.get_model_statistics()
        
        assert 'models' in stats
        assert 'total_calls' in stats
        assert 'gemini' in stats['models']
        assert 'deepseek' in stats['models']
        # Claude removed from dual-model architecture
        assert 'claude' not in stats['models']


class TestAlertManager:
    """Test alert manager with KRW support"""
    
    @pytest.mark.asyncio
    async def test_alert_manager_initialization(self):
        """Test alert manager initialization"""
        from openclaw.skills.monitoring.alert_manager import AlertManager
        
        manager = AlertManager()
        
        assert hasattr(manager, 'currency_converter')
        assert hasattr(manager, 'alerts')
    
    @pytest.mark.asyncio
    async def test_krw_price_formatting_in_alert(self):
        """Test KRW formatting in alert messages"""
        from openclaw.skills.monitoring.alert_manager import AlertManager
        
        manager = AlertManager()
        
        # Test signal alert
        signal = {
            'action': 'BUY',
            'strategy': 'Test Strategy',
            'price': 100.0,  # Will be converted to KRW
            'stop_loss': 98.0,
            'take_profit': 105.0,
            'confidence': 0.8,
            'reason': 'Test reason',
            'max_hold_hours': 6
        }
        
        alert = await manager.generate_short_term_signal_alert('AAPL', signal)
        
        # Alert should contain KRW symbol
        assert '₩' in alert
        assert 'BUY' in alert
        assert 'AAPL' in alert
    
    def test_percentage_formatting_in_report(self):
        """Test percentage formatting"""
        from openclaw.skills.monitoring.alert_manager import AlertManager
        
        manager = AlertManager()
        
        # Test format percentage helper
        formatted = manager._format_percentage(0.025)
        assert '+' in formatted or '2.5' in str(formatted)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
