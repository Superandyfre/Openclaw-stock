"""
自动市场监控系统

功能：
1. 定时监控加密货币（每小时一次）
2. 检测关键信号变化（买入/卖出机会）
3. 生成每日报告
4. 异常告警（价格剧烈波动、情绪极端）
"""
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
from pathlib import Path
import json

try:
    from openclaw.skills.analysis.enhanced_ai_trading_advisor import EnhancedAITradingAdvisor
    ADVISOR_AVAILABLE = True
except ImportError:
    logger.warning("增强版AI交易顾问未找到")
    ADVISOR_AVAILABLE = False


class AutoMarketMonitor:
    """自动市场监控系统"""
    
    def __init__(
        self,
        symbols: List[Tuple[str, str]] = None,
        check_interval_minutes: int = 60,
        alert_threshold: Dict[str, float] = None,
        save_reports: bool = True,
        reports_dir: str = './reports'
    ):
        """
        初始化监控系统
        
        Args:
            symbols: 监控的交易对列表 [(binance_symbol, coingecko_id), ...]
            check_interval_minutes: 检查间隔（分钟）
            alert_threshold: 告警阈值 {
                'price_change_24h': 10.0,  # 24h涨跌超过10%
                'fear_greed_extreme': 20,   # 恐慌贪婪指数极端值
                'confidence_high': 0.75     # 信号置信度高于75%
            }
            save_reports: 是否保存报告
            reports_dir: 报告保存目录
        """
        self.symbols = symbols or [
            ('BTCUSDT', 'bitcoin'),
            ('ETHUSDT', 'ethereum'),
        ]
        
        self.check_interval_minutes = check_interval_minutes
        
        self.alert_threshold = alert_threshold or {
            'price_change_24h': 10.0,
            'fear_greed_extreme': 20,
            'confidence_high': 0.75
        }
        
        self.save_reports = save_reports
        self.reports_dir = Path(reports_dir)
        
        if self.save_reports:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化AI顾问
        if ADVISOR_AVAILABLE:
            self.advisor = EnhancedAITradingAdvisor(enable_derivatives=False)
        else:
            logger.error("AI顾问不可用，监控系统无法启动")
            self.advisor = None
        
        # 监控历史
        self.monitor_history: Dict[str, List[Dict[str, Any]]] = {}
        for symbol, _ in self.symbols:
            self.monitor_history[symbol] = []
        
        # 告警记录
        self.alerts: List[Dict[str, Any]] = []
        
        logger.info(f"✅ AutoMarketMonitor 初始化成功")
        logger.info(f"   监控{len(self.symbols)}个交易对，间隔{check_interval_minutes}分钟")
    
    async def check_single_symbol(
        self,
        binance_symbol: str,
        coingecko_id: str
    ) -> Dict[str, Any]:
        """检查单个交易对"""
        
        logger.info(f"🔍 检查 {binance_symbol}...")
        
        try:
            # 执行综合分析
            result = await self.advisor.analyze_crypto(
                symbol=binance_symbol,
                coin_id=coingecko_id,
                depth_levels=20
            )
            
            # 记录历史
            self.monitor_history[binance_symbol].append(result)
            
            # 限制历史长度（保留最近100条）
            if len(self.monitor_history[binance_symbol]) > 100:
                self.monitor_history[binance_symbol] = self.monitor_history[binance_symbol][-100:]
            
            # 检查告警条件
            await self._check_alerts(binance_symbol, result)
            
            return result
        
        except Exception as e:
            logger.error(f"检查{binance_symbol}失败: {e}")
            return {"error": str(e)}
    
    async def _check_alerts(self, symbol: str, result: Dict[str, Any]):
        """检查告警条件"""
        
        alerts_triggered = []
        data = result.get('data', {})
        recommendation = result.get('recommendation', {})
        
        # 1. 价格剧烈波动告警
        if self.monitor_history[symbol]:
            last_result = self.monitor_history[symbol][-2] if len(self.monitor_history[symbol]) >= 2 else None
            if last_result:
                last_price = last_result.get('data', {}).get('current_price')
                current_price = data.get('current_price')
                
                if last_price and current_price:
                    price_change = abs((current_price - last_price) / last_price * 100)
                    
                    if price_change >= self.alert_threshold['price_change_24h']:
                        alerts_triggered.append({
                            'type': 'PRICE_VOLATILITY',
                            'symbol': symbol,
                            'message': f"价格剧烈波动: {price_change:+.2f}% (${last_price:,.2f} → ${current_price:,.2f})",
                            'severity': 'HIGH'
                        })
        
        # 2. 恐慌贪婪指数极端告警
        fg_index = data.get('fear_greed_index')
        if fg_index is not None:
            if fg_index <= self.alert_threshold['fear_greed_extreme']:
                alerts_triggered.append({
                    'type': 'EXTREME_FEAR',
                    'symbol': symbol,
                    'message': f"极度恐慌: {fg_index}/100 - 可能存在买入机会",
                    'severity': 'MEDIUM'
                })
            elif fg_index >= (100 - self.alert_threshold['fear_greed_extreme']):
                alerts_triggered.append({
                    'type': 'EXTREME_GREED',
                    'symbol': symbol,
                    'message': f"极度贪婪: {fg_index}/100 - 考虑获利了结",
                    'severity': 'MEDIUM'
                })
        
        # 3. 高置信度买卖信号告警
        if recommendation:
            confidence = recommendation.get('confidence', 0)
            action = recommendation.get('action', 'NEUTRAL')
            
            if confidence >= self.alert_threshold['confidence_high'] and action != 'NEUTRAL':
                alerts_triggered.append({
                    'type': 'STRONG_SIGNAL',
                    'symbol': symbol,
                    'message': f"强烈{action}信号: 置信度{confidence:.1%}",
                    'severity': 'HIGH',
                    'action': action,
                    'confidence': confidence
                })
        
        # 记录告警
        for alert in alerts_triggered:
            alert['timestamp'] = datetime.now().isoformat()
            self.alerts.append(alert)
            
            # 打印告警
            logger.warning(f"⚠️  【告警】{alert['message']}")
    
    async def check_all_symbols(self) -> List[Dict[str, Any]]:
        """检查所有交易对"""
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 开始监控检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}")
        
        results = []
        
        for binance_symbol, coingecko_id in self.symbols:
            result = await self.check_single_symbol(binance_symbol, coingecko_id)
            results.append(result)
            
            # 避免速率限制
            await asyncio.sleep(2)
        
        logger.info(f"\n✅ 本轮监控完成\n")
        
        return results
    
    async def generate_daily_report(self) -> str:
        """生成每日报告"""
        
        logger.info("📊 生成每日报告...")
        
        lines = []
        lines.append("=" * 80)
        lines.append(f"📈 加密货币市场每日监控报告")
        lines.append(f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
        lines.append("=" * 80)
        lines.append("")
        
        # 1. 概览
        lines.append("【市场概览】")
        for symbol, _ in self.symbols:
            if self.monitor_history[symbol]:
                latest = self.monitor_history[symbol][-1]
                data = latest.get('data', {})
                
                price = data.get('current_price', 0)
                fg_index = data.get('fear_greed_index')
                
                rec = latest.get('recommendation', {})
                action = rec.get('action', 'N/A')
                confidence = rec.get('confidence', 0)
                
                lines.append(f"\n{symbol}:")
                lines.append(f"  价格: ${price:,.2f}")
                if fg_index is not None:
                    fg_label = "极度恐慌" if fg_index < 25 else "恐慌" if fg_index < 45 else "中性" if fg_index < 55 else "贪婪" if fg_index < 75 else "极度贪婪"
                    lines.append(f"  恐慌贪婪: {fg_index}/100 ({fg_label})")
                lines.append(f"  建议: {action} (置信度: {confidence:.1%})")
        
        lines.append("")
        
        # 2. 告警汇总（最近24小时）
        lines.append("【告警汇总】")
        recent_alerts = [
            a for a in self.alerts
            if datetime.fromisoformat(a['timestamp']) > datetime.now() - timedelta(hours=24)
        ]
        
        if recent_alerts:
            high_severity = [a for a in recent_alerts if a['severity'] == 'HIGH']
            medium_severity = [a for a in recent_alerts if a['severity'] == 'MEDIUM']
            
            lines.append(f"  高级告警: {len(high_severity)}条")
            lines.append(f"  中级告警: {len(medium_severity)}条")
            lines.append("")
            
            for alert in recent_alerts[-5:]:  # 最近5条
                time_str = datetime.fromisoformat(alert['timestamp']).strftime('%H:%M')
                lines.append(f"  [{time_str}] {alert['symbol']}: {alert['message']}")
        else:
            lines.append("  无告警")
        
        lines.append("")
        
        # 3. 交易建议
        lines.append("【交易建议】")
        for symbol, _ in self.symbols:
            if self.monitor_history[symbol]:
                latest = self.monitor_history[symbol][-1]
                rec = latest.get('recommendation', {})
                
                if rec and rec.get('action') != 'NEUTRAL' and rec.get('confidence', 0) >= 0.6:
                    lines.append(f"\n{symbol}:")
                    lines.append(f"  {self.advisor.get_summary_report(latest)}")
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("报告结束")
        lines.append("=" * 80)
        
        report = "\n".join(lines)
        
        # 保存报告
        if self.save_reports:
            report_file = self.reports_dir / f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
            report_file.write_text(report, encoding='utf-8')
            logger.info(f"📄 报告已保存: {report_file}")
        
        return report
    
    async def run_once(self):
        """运行一次完整检查"""
        await self.check_all_symbols()
    
    async def run_continuous(self):
        """持续运行监控"""
        
        logger.info(f"🚀 开始持续监控...")
        logger.info(f"   检查间隔: {self.check_interval_minutes}分钟")
        logger.info(f"   监控对象: {', '.join(s[0] for s in self.symbols)}")
        
        while True:
            try:
                # 执行检查
                await self.check_all_symbols()
                
                # 等待下一次检查
                logger.info(f"⏰ 等待{self.check_interval_minutes}分钟后再次检查...")
                await asyncio.sleep(self.check_interval_minutes * 60)
            
            except KeyboardInterrupt:
                logger.info("⏹️  监控已停止")
                break
            except Exception as e:
                logger.error(f"监控出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟
    
    def get_alerts_summary(self, hours: int = 24) -> str:
        """获取告警摘要"""
        
        recent_alerts = [
            a for a in self.alerts
            if datetime.fromisoformat(a['timestamp']) > datetime.now() - timedelta(hours=hours)
        ]
        
        if not recent_alerts:
            return f"📭 最近{hours}小时无告警"
        
        lines = [f"📬 最近{hours}小时告警 ({len(recent_alerts)}条):"]
        for alert in recent_alerts[-10:]:
            time_str = datetime.fromisoformat(alert['timestamp']).strftime('%m-%d %H:%M')
            lines.append(f"  [{time_str}] {alert['symbol']}: {alert['message']}")
        
        return "\n".join(lines)


if __name__ == '__main__':
    # 测试
    async def test():
        # 创建监控器
        monitor = AutoMarketMonitor(
            symbols=[('BTCUSDT', 'bitcoin'), ('ETHUSDT', 'ethereum')],
            check_interval_minutes=60,
            save_reports=True,
            reports_dir='./reports'
        )
        
        # 运行一次检查
        await monitor.run_once()
        
        # 生成报告
        report = await monitor.generate_daily_report()
        print("\n" + report)
        
        # 显示告警
        print("\n" + monitor.get_alerts_summary(hours=24))
    
    asyncio.run(test())
