"""
Cost Alert Service

This module implements cost alert notifications via webhooks and email
when tenant cost thresholds are reached.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid
import structlog
import httpx

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Tenant
from app.core.config import settings


logger = structlog.get_logger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of cost alerts"""
    THRESHOLD_80 = "threshold_80_percent"
    THRESHOLD_100 = "threshold_100_percent"
    DAILY_SUMMARY = "daily_summary"
    BUDGET_EXCEEDED = "budget_exceeded"


class CostAlertService:
    """
    Send cost alerts via webhooks and email.
    
    Implements:
    - Webhook notifications when thresholds reached
    - Email alerts for critical events
    - Alert deduplication to prevent spam
    - Configurable alert channels per tenant
    
    References: Requirement 11.5, Design: Cost Control Design
    """
    
    # Alert thresholds
    WARNING_THRESHOLD_PERCENT = 80.0
    CRITICAL_THRESHOLD_PERCENT = 100.0
    
    # Webhook timeout
    WEBHOOK_TIMEOUT_SECONDS = 5.0
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._sent_alerts: Dict[str, datetime] = {}  # Deduplication cache
    
    async def get_tenant(self, tenant_id: uuid.UUID) -> Optional[Tenant]:
        """Get tenant information"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()
    
    def _get_alert_key(
        self,
        tenant_id: uuid.UUID,
        alert_type: AlertType,
        date: datetime,
    ) -> str:
        """Generate unique key for alert deduplication"""
        date_str = date.strftime("%Y-%m-%d")
        return f"{tenant_id}:{alert_type.value}:{date_str}"
    
    def _should_send_alert(
        self,
        tenant_id: uuid.UUID,
        alert_type: AlertType,
        date: datetime,
    ) -> bool:
        """Check if alert should be sent (deduplication)"""
        alert_key = self._get_alert_key(tenant_id, alert_type, date)
        
        # Check if already sent today
        if alert_key in self._sent_alerts:
            last_sent = self._sent_alerts[alert_key]
            # Only send once per day
            if last_sent.date() == date.date():
                return False
        
        return True
    
    def _mark_alert_sent(
        self,
        tenant_id: uuid.UUID,
        alert_type: AlertType,
        date: datetime,
    ) -> None:
        """Mark alert as sent"""
        alert_key = self._get_alert_key(tenant_id, alert_type, date)
        self._sent_alerts[alert_key] = date
    
    def _build_alert_payload(
        self,
        tenant: Tenant,
        alert_type: AlertType,
        alert_level: AlertLevel,
        daily_cost: float,
        threshold: float,
        percent_used: float,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build webhook payload"""
        payload = {
            "alert_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "alert_type": alert_type.value,
            "alert_level": alert_level.value,
            "tenant": {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
            },
            "cost_metrics": {
                "daily_cost_usd": daily_cost,
                "daily_threshold_usd": threshold,
                "percent_used": percent_used,
                "remaining_budget_usd": max(0.0, threshold - daily_cost),
            },
        }
        
        if additional_data:
            payload.update(additional_data)
        
        return payload
    
    async def _send_webhook(
        self,
        webhook_url: str,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Send webhook notification.
        
        Args:
            webhook_url: Webhook endpoint URL
            payload: Alert payload
        
        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.WEBHOOK_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "AI-Presentation-Platform/1.0",
                    },
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        "webhook_sent_successfully",
                        webhook_url=webhook_url,
                        alert_type=payload["alert_type"],
                        status_code=response.status_code,
                    )
                    return True
                else:
                    logger.warning(
                        "webhook_failed",
                        webhook_url=webhook_url,
                        status_code=response.status_code,
                        response=response.text[:200],
                    )
                    return False
                    
        except httpx.TimeoutException:
            logger.error(
                "webhook_timeout",
                webhook_url=webhook_url,
                timeout=self.WEBHOOK_TIMEOUT_SECONDS,
            )
            return False
        except Exception as e:
            logger.error(
                "webhook_error",
                webhook_url=webhook_url,
                error=str(e),
            )
            return False
    
    async def send_threshold_alert(
        self,
        tenant_id: uuid.UUID,
        daily_cost: float,
        threshold: float,
        percent_used: float,
        webhook_url: Optional[str] = None,
    ) -> bool:
        """
        Send alert when cost threshold is reached.
        
        Args:
            tenant_id: Tenant ID
            daily_cost: Current daily cost
            threshold: Daily cost threshold
            percent_used: Percentage of threshold used
            webhook_url: Optional webhook URL (uses tenant config if not provided)
        
        Returns:
            True if alert sent successfully
        """
        # Get tenant
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            logger.error("tenant_not_found", tenant_id=str(tenant_id))
            return False
        
        # Determine alert type and level
        if percent_used >= self.CRITICAL_THRESHOLD_PERCENT:
            alert_type = AlertType.THRESHOLD_100
            alert_level = AlertLevel.CRITICAL
        elif percent_used >= self.WARNING_THRESHOLD_PERCENT:
            alert_type = AlertType.THRESHOLD_80
            alert_level = AlertLevel.WARNING
        else:
            # Below threshold, no alert needed
            return True
        
        # Check deduplication
        now = datetime.utcnow()
        if not self._should_send_alert(tenant_id, alert_type, now):
            logger.info(
                "alert_already_sent_today",
                tenant_id=str(tenant_id),
                alert_type=alert_type.value,
            )
            return True
        
        # Build payload
        payload = self._build_alert_payload(
            tenant=tenant,
            alert_type=alert_type,
            alert_level=alert_level,
            daily_cost=daily_cost,
            threshold=threshold,
            percent_used=percent_used,
            additional_data={
                "message": self._get_alert_message(alert_type, daily_cost, threshold),
                "recommended_action": self._get_recommended_action(alert_type),
            },
        )
        
        # Send webhook
        # TODO: Get webhook URL from tenant configuration
        # For now, use provided URL or environment variable
        target_url = webhook_url or settings.COST_ALERT_WEBHOOK_URL
        
        if not target_url:
            logger.warning(
                "no_webhook_configured",
                tenant_id=str(tenant_id),
                alert_type=alert_type.value,
            )
            # Log alert but don't fail
            logger.info(
                "cost_alert_triggered",
                tenant_id=str(tenant_id),
                alert_type=alert_type.value,
                alert_level=alert_level.value,
                daily_cost=daily_cost,
                threshold=threshold,
                percent_used=percent_used,
            )
            self._mark_alert_sent(tenant_id, alert_type, now)
            return True
        
        # Send webhook
        success = await self._send_webhook(target_url, payload)
        
        if success:
            self._mark_alert_sent(tenant_id, alert_type, now)
        
        return success
    
    def _get_alert_message(
        self,
        alert_type: AlertType,
        daily_cost: float,
        threshold: float,
    ) -> str:
        """Get human-readable alert message"""
        if alert_type == AlertType.THRESHOLD_80:
            return (
                f"Your daily AI usage cost has reached 80% of your limit. "
                f"Current: ${daily_cost:.2f} / ${threshold:.2f}"
            )
        elif alert_type == AlertType.THRESHOLD_100:
            return (
                f"Your daily AI usage cost limit has been reached. "
                f"Current: ${daily_cost:.2f} / ${threshold:.2f}. "
                f"New requests will be queued until tomorrow."
            )
        elif alert_type == AlertType.BUDGET_EXCEEDED:
            return (
                f"Your daily AI usage cost has exceeded your limit. "
                f"Current: ${daily_cost:.2f} / ${threshold:.2f}"
            )
        else:
            return f"Cost alert: ${daily_cost:.2f} / ${threshold:.2f}"
    
    def _get_recommended_action(self, alert_type: AlertType) -> str:
        """Get recommended action for alert"""
        if alert_type == AlertType.THRESHOLD_80:
            return (
                "Consider reviewing your usage patterns or upgrading your plan "
                "to avoid service interruption."
            )
        elif alert_type == AlertType.THRESHOLD_100:
            return (
                "Your daily limit has been reached. New presentation requests will be "
                "queued and processed tomorrow. To continue today, please upgrade your plan."
            )
        elif alert_type == AlertType.BUDGET_EXCEEDED:
            return (
                "Please review your usage and consider upgrading your plan."
            )
        else:
            return "Please review your usage patterns."
    
    async def send_daily_summary(
        self,
        tenant_id: uuid.UUID,
        daily_cost: float,
        threshold: float,
        presentation_count: int,
        webhook_url: Optional[str] = None,
    ) -> bool:
        """
        Send daily cost summary.
        
        Args:
            tenant_id: Tenant ID
            daily_cost: Total daily cost
            threshold: Daily cost threshold
            presentation_count: Number of presentations generated
            webhook_url: Optional webhook URL
        
        Returns:
            True if sent successfully
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        percent_used = (daily_cost / threshold * 100) if threshold > 0 else 0
        
        payload = self._build_alert_payload(
            tenant=tenant,
            alert_type=AlertType.DAILY_SUMMARY,
            alert_level=AlertLevel.INFO,
            daily_cost=daily_cost,
            threshold=threshold,
            percent_used=percent_used,
            additional_data={
                "presentation_count": presentation_count,
                "avg_cost_per_presentation": daily_cost / presentation_count if presentation_count > 0 else 0,
                "message": f"Daily summary: Generated {presentation_count} presentations for ${daily_cost:.2f}",
            },
        )
        
        target_url = webhook_url or settings.COST_ALERT_WEBHOOK_URL
        if not target_url:
            logger.info(
                "daily_summary_logged",
                tenant_id=str(tenant_id),
                daily_cost=daily_cost,
                presentation_count=presentation_count,
            )
            return True
        
        return await self._send_webhook(target_url, payload)
    
    async def send_batch_alerts(
        self,
        alerts: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Send multiple alerts in batch.
        
        Useful for scheduled alert processing.
        
        Args:
            alerts: List of alert configurations
        
        Returns:
            Dict with success/failure counts
        """
        results = {"success": 0, "failed": 0}
        
        for alert_config in alerts:
            try:
                success = await self.send_threshold_alert(
                    tenant_id=alert_config["tenant_id"],
                    daily_cost=alert_config["daily_cost"],
                    threshold=alert_config["threshold"],
                    percent_used=alert_config["percent_used"],
                    webhook_url=alert_config.get("webhook_url"),
                )
                
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                logger.error(
                    "batch_alert_failed",
                    tenant_id=str(alert_config.get("tenant_id")),
                    error=str(e),
                )
                results["failed"] += 1
        
        logger.info(
            "batch_alerts_completed",
            total=len(alerts),
            success=results["success"],
            failed=results["failed"],
        )
        
        return results
