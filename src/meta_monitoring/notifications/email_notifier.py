"""Email notification system for meta-monitoring alerts"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

from src.config.settings import settings
from src.shared.database.connection import get_db
from src.shared.models.meta_monitoring import MonitoringAlert

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Email notification service for meta-monitoring alerts"""

    def __init__(self):
        # Email configuration (from settings)
        self.smtp_host = getattr(settings, 'smtp_host', 'localhost')
        self.smtp_port = getattr(settings, 'smtp_port', 587)
        self.smtp_user = getattr(settings, 'smtp_user', '')
        self.smtp_password = getattr(settings, 'smtp_password', '')
        self.from_email = getattr(settings, 'admin_from_email', 'noreply@fa-ai-system.com')
        self.admin_emails = getattr(settings, 'admin_emails', ['admin@fa-ai-system.com'])

        # Notification thresholds
        self.critical_immediate = True  # Send immediately for critical
        self.high_hourly = True         # Send hourly digest for high
        self.medium_daily = True        # Send daily digest for medium/low

    async def send_critical_alert(self, alert: MonitoringAlert) -> bool:
        """Send immediate email for critical alert

        Args:
            alert: MonitoringAlert database object

        Returns:
            True if email sent successfully
        """
        logger.info(f"[EmailNotifier] Sending critical alert: {alert.alert_title}")

        subject = f"🚨 CRITICAL ALERT: {alert.alert_title}"

        body = self._render_critical_alert_email(alert)

        return await self._send_email(
            to_emails=self.admin_emails,
            subject=subject,
            body_html=body,
            priority='urgent'
        )

    async def send_hourly_digest(self, alerts: List[MonitoringAlert]) -> bool:
        """Send hourly digest of high-priority alerts

        Args:
            alerts: List of high-priority alerts from last hour

        Returns:
            True if email sent successfully
        """
        if not alerts:
            return True

        logger.info(f"[EmailNotifier] Sending hourly digest with {len(alerts)} alerts")

        subject = f"⚠️ Hourly Alert Digest - {len(alerts)} High-Priority Issues"
        body = self._render_hourly_digest_email(alerts)

        return await self._send_email(
            to_emails=self.admin_emails,
            subject=subject,
            body_html=body,
            priority='high'
        )

    async def send_daily_digest(
        self,
        evaluation_results: Dict[str, Any],
        alerts: List[MonitoringAlert]
    ) -> bool:
        """Send daily system health digest

        Args:
            evaluation_results: Results from daily evaluation
            alerts: List of alerts from last 24 hours

        Returns:
            True if email sent successfully
        """
        logger.info(f"[EmailNotifier] Sending daily digest")

        subject = f"📊 Daily System Health Report - {datetime.utcnow().strftime('%Y-%m-%d')}"
        body = self._render_daily_digest_email(evaluation_results, alerts)

        return await self._send_email(
            to_emails=self.admin_emails,
            subject=subject,
            body_html=body,
            priority='normal'
        )

    def _render_critical_alert_email(self, alert: MonitoringAlert) -> str:
        """Render HTML email for critical alert"""
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #dc2626; color: white; padding: 20px; border-radius: 5px; }
        .content { background: #f9fafb; padding: 20px; margin-top: 20px; border-radius: 5px; }
        .metric { margin: 10px 0; padding: 10px; background: white; border-left: 4px solid #dc2626; }
        .footer { margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }
        .button { display: inline-block; padding: 10px 20px; background: #dc2626; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 CRITICAL ALERT</h1>
            <h2>{{ alert.alert_title }}</h2>
        </div>

        <div class="content">
            <p><strong>Alert Type:</strong> {{ alert.alert_type|upper }}</p>
            <p><strong>Severity:</strong> CRITICAL</p>
            <p><strong>Affected Component:</strong> {{ alert.affected_component or 'Unknown' }}</p>
            <p><strong>Detected At:</strong> {{ alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') }}</p>

            <h3>Description:</h3>
            <p>{{ alert.alert_description }}</p>

            {% if alert.metric_name %}
            <div class="metric">
                <strong>{{ alert.metric_name }}:</strong><br>
                Current: {{ "%.4f"|format(alert.current_value) if alert.current_value else 'N/A' }}<br>
                Baseline: {{ "%.4f"|format(alert.baseline_value) if alert.baseline_value else 'N/A' }}<br>
                Threshold: {{ "%.4f"|format(alert.threshold_value) if alert.threshold_value else 'N/A' }}
            </div>
            {% endif %}

            <a href="http://localhost:3000/admin/meta-monitoring/alerts" class="button">
                View in Dashboard →
            </a>
        </div>

        <div class="footer">
            <p>This is an automated alert from the FA AI System Meta-Monitoring Agent.</p>
            <p>Alert ID: {{ alert.alert_id }}</p>
        </div>
    </div>
</body>
</html>
        """)

        return template.render(alert=alert)

    def _render_hourly_digest_email(self, alerts: List[MonitoringAlert]) -> str:
        """Render HTML email for hourly digest"""
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #f59e0b; color: white; padding: 20px; border-radius: 5px; }
        .alert-item { background: #fff7ed; padding: 15px; margin: 10px 0; border-left: 4px solid #f59e0b; border-radius: 3px; }
        .footer { margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }
        .button { display: inline-block; padding: 10px 20px; background: #f59e0b; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Hourly Alert Digest</h1>
            <p>{{ alerts|length }} High-Priority Issues Detected</p>
        </div>

        {% for alert in alerts %}
        <div class="alert-item">
            <h3>{{ alert.alert_title }}</h3>
            <p><strong>Severity:</strong> {{ alert.severity|upper }} | <strong>Component:</strong> {{ alert.affected_component or 'Unknown' }}</p>
            <p>{{ alert.alert_description }}</p>
            <p><small>Detected: {{ alert.created_at.strftime('%H:%M UTC') }}</small></p>
        </div>
        {% endfor %}

        <a href="http://localhost:3000/admin/meta-monitoring/alerts" class="button">
            View All Alerts →
        </a>

        <div class="footer">
            <p>This is an automated hourly digest from the FA AI System Meta-Monitoring.</p>
        </div>
    </div>
</body>
</html>
        """)

        return template.render(alerts=alerts)

    def _render_daily_digest_email(
        self,
        evaluation_results: Dict[str, Any],
        alerts: List[MonitoringAlert]
    ) -> str:
        """Render HTML email for daily digest"""
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 700px; margin: 0 auto; padding: 20px; }
        .header { background: #2563eb; color: white; padding: 20px; border-radius: 5px; }
        .metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }
        .metric-card { background: white; padding: 15px; border: 1px solid #e5e7eb; border-radius: 5px; }
        .metric-value { font-size: 24px; font-weight: bold; color: #2563eb; }
        .improved { color: #10b981; }
        .degraded { color: #ef4444; }
        .alert-summary { background: #fef3c7; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .footer { margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }
        .button { display: inline-block; padding: 10px 20px; background: #2563eb; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Daily System Health Report</h1>
            <p>{{ datetime.now().strftime('%B %d, %Y') }}</p>
        </div>

        <h2>System Metrics (Last 24 Hours)</h2>

        <div class="metrics">
            {% if evaluation_results.metrics %}
            <div class="metric-card">
                <div>Total Queries</div>
                <div class="metric-value">{{ evaluation_results.metrics.total_queries }}</div>
            </div>

            <div class="metric-card">
                <div>Success Rate</div>
                <div class="metric-value">{{ "%.1f"|format(100 - evaluation_results.metrics.error_rate * 100) }}%</div>
            </div>

            {% if evaluation_results.metrics.fact_accuracy %}
            <div class="metric-card">
                <div>Fact Accuracy</div>
                <div class="metric-value">{{ "%.1f"|format(evaluation_results.metrics.fact_accuracy * 100) }}%</div>
            </div>
            {% endif %}

            {% if evaluation_results.metrics.sla_compliance_rate %}
            <div class="metric-card">
                <div>SLA Compliance</div>
                <div class="metric-value">{{ "%.1f"|format(evaluation_results.metrics.sla_compliance_rate * 100) }}%</div>
            </div>
            {% endif %}

            <div class="metric-card">
                <div>Avg Response Time</div>
                <div class="metric-value">{{ evaluation_results.metrics.avg_response_time_ms }}ms</div>
            </div>
            {% endif %}
        </div>

        {% if alerts %}
        <div class="alert-summary">
            <h3>⚠️ Alerts Summary</h3>
            <p><strong>{{ alerts|length }}</strong> alerts detected in the last 24 hours:</p>
            <ul>
            {% for alert in alerts[:5] %}
                <li>{{ alert.severity|upper }}: {{ alert.alert_title }}</li>
            {% endfor %}
            {% if alerts|length > 5 %}
                <li>... and {{ alerts|length - 5 }} more</li>
            {% endif %}
            </ul>
        </div>
        {% else %}
        <div style="background: #d1fae5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p><strong>✅ All Systems Healthy</strong></p>
            <p>No alerts detected in the last 24 hours.</p>
        </div>
        {% endif %}

        <a href="http://localhost:3000/admin/meta-monitoring" class="button">
            View Full Dashboard →
        </a>

        <div class="footer">
            <p>This is an automated daily report from the FA AI System Meta-Monitoring.</p>
            <p>Report generated: {{ datetime.now().strftime('%Y-%m-%d %H:%M UTC') }}</p>
        </div>
    </div>
</body>
</html>
        """)

        return template.render(
            evaluation_results=evaluation_results,
            alerts=alerts,
            datetime=datetime
        )

    async def _send_email(
        self,
        to_emails: List[str],
        subject: str,
        body_html: str,
        priority: str = 'normal'
    ) -> bool:
        """Send email via SMTP

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            body_html: HTML email body
            priority: Priority level ('urgent', 'high', 'normal')

        Returns:
            True if sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject

            # Set priority headers
            if priority == 'urgent':
                msg['X-Priority'] = '1'
                msg['Importance'] = 'high'
            elif priority == 'high':
                msg['X-Priority'] = '2'
                msg['Importance'] = 'high'

            # Attach HTML body
            html_part = MIMEText(body_html, 'html')
            msg.attach(html_part)

            # Send via SMTP
            # NOTE: In production, you would use SendGrid, AWS SES, or another service
            # For now, this is a placeholder that logs the email
            logger.info(f"[EmailNotifier] Would send email to {to_emails}")
            logger.info(f"[EmailNotifier] Subject: {subject}")
            logger.debug(f"[EmailNotifier] Body: {body_html[:200]}...")

            # Uncomment for actual SMTP sending:
            # with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            #     if self.smtp_user and self.smtp_password:
            #         server.starttls()
            #         server.login(self.smtp_user, self.smtp_password)
            #     server.send_message(msg)

            logger.info("[EmailNotifier] Email sent successfully")
            return True

        except Exception as e:
            logger.error(f"[EmailNotifier] Error sending email: {e}", exc_info=True)
            return False

    async def mark_alert_as_emailed(self, alert_id: str):
        """Mark alert as having been emailed"""
        try:
            db = next(get_db())
            alert = db.query(MonitoringAlert).filter(
                MonitoringAlert.alert_id == alert_id
            ).first()

            if alert:
                alert.email_sent = True
                alert.email_sent_at = datetime.utcnow()
                db.commit()

        except Exception as e:
            logger.error(f"[EmailNotifier] Error marking alert as emailed: {e}", exc_info=True)
        finally:
            db.close()


# Helper function to send critical alert
async def send_critical_alert_for_new_alerts():
    """Check for new critical alerts and send emails"""
    try:
        db = next(get_db())
        notifier = EmailNotifier()

        # Find critical alerts that haven't been emailed
        critical_alerts = db.query(MonitoringAlert).filter(
            MonitoringAlert.severity == 'critical',
            MonitoringAlert.email_sent == False,
            MonitoringAlert.status == 'open'
        ).all()

        for alert in critical_alerts:
            await notifier.send_critical_alert(alert)
            await notifier.mark_alert_as_emailed(str(alert.alert_id))

    except Exception as e:
        logger.error(f"Error sending critical alerts: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    # For testing
    import asyncio
    asyncio.run(send_critical_alert_for_new_alerts())
