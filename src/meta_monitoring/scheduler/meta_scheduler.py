"""Automated scheduler for meta-monitoring tasks"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging
import asyncio

from src.config.settings import settings
from src.shared.database.connection import get_db
from src.meta_monitoring.agents.monitoring_agent import run_monitoring_agent
from src.meta_monitoring.agents.evaluation_agent import run_evaluation_agent
from src.meta_monitoring.notifications.email_notifier import EmailNotifier
from src.shared.models.meta_monitoring import MonitoringAlert

logger = logging.getLogger(__name__)


class MetaMonitoringScheduler:
    """Scheduler for automated meta-monitoring tasks"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.email_notifier = EmailNotifier()
        self.is_running = False

    def start(self):
        """Start the scheduler with all configured jobs"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        logger.info("[MetaScheduler] Configuring scheduled jobs...")

        # Job 1: Continuous monitoring every 5 minutes
        self.scheduler.add_job(
            self._run_monitoring_cycle,
            trigger=IntervalTrigger(minutes=5),
            id='monitoring_cycle',
            name='Continuous Error Monitoring',
            replace_existing=True,
            max_instances=1
        )
        logger.info("[MetaScheduler] ✓ Monitoring cycle: every 5 minutes")

        # Job 2: Daily evaluation at 3 AM
        self.scheduler.add_job(
            self._run_daily_evaluation,
            trigger=CronTrigger(hour=3, minute=0),
            id='daily_evaluation',
            name='Daily Quality Evaluation',
            replace_existing=True,
            max_instances=1
        )
        logger.info("[MetaScheduler] ✓ Daily evaluation: 3:00 AM")

        # Job 3: Hourly alert digest
        self.scheduler.add_job(
            self._send_hourly_digest,
            trigger=CronTrigger(minute=0),  # Top of every hour
            id='hourly_digest',
            name='Hourly Alert Digest',
            replace_existing=True,
            max_instances=1
        )
        logger.info("[MetaScheduler] ✓ Hourly digest: top of every hour")

        # Job 4: Daily health report at 9 AM
        self.scheduler.add_job(
            self._send_daily_health_report,
            trigger=CronTrigger(hour=9, minute=0),
            id='daily_health_report',
            name='Daily Health Report',
            replace_existing=True,
            max_instances=1
        )
        logger.info("[MetaScheduler] ✓ Daily health report: 9:00 AM")

        # Start the scheduler
        self.scheduler.start()
        self.is_running = True
        logger.info("[MetaScheduler] 🚀 Scheduler started successfully with 4 jobs")

    def stop(self):
        """Stop the scheduler gracefully"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        logger.info("[MetaScheduler] Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("[MetaScheduler] ✓ Scheduler stopped")

    def get_jobs(self):
        """Get list of scheduled jobs"""
        jobs = self.scheduler.get_jobs()
        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            }
            for job in jobs
        ]

    async def _run_monitoring_cycle(self):
        """Execute monitoring cycle (every 5 minutes)"""
        try:
            logger.info("[MetaScheduler] Starting scheduled monitoring cycle...")
            start_time = datetime.utcnow()

            # Run monitoring agent
            alerts = await run_monitoring_agent()

            # Send immediate emails for critical alerts
            if alerts:
                critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
                for alert_data in critical_alerts:
                    # Get the alert from database to send email
                    db = next(get_db())
                    try:
                        alert = db.query(MonitoringAlert).filter(
                            MonitoringAlert.alert_id == alert_data['alert_id']
                        ).first()
                        if alert:
                            await self.email_notifier.send_critical_alert(alert)
                    finally:
                        db.close()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"[MetaScheduler] ✓ Monitoring cycle completed in {duration:.2f}s: "
                f"{len(alerts)} alerts created"
            )

        except Exception as e:
            logger.error(f"[MetaScheduler] Error in monitoring cycle: {e}", exc_info=True)

    async def _run_daily_evaluation(self):
        """Execute daily evaluation (3 AM)"""
        try:
            logger.info("[MetaScheduler] Starting scheduled daily evaluation...")
            start_time = datetime.utcnow()

            # Run evaluation agent
            results = await run_evaluation_agent(run_type="daily")

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"[MetaScheduler] ✓ Daily evaluation completed in {duration:.2f}s: "
                f"{results.get('total_queries_evaluated', 0)} queries evaluated"
            )

            # Evaluation results will be included in daily health report at 9 AM

        except Exception as e:
            logger.error(f"[MetaScheduler] Error in daily evaluation: {e}", exc_info=True)

    async def _send_hourly_digest(self):
        """Send hourly digest of high-priority alerts (top of every hour)"""
        try:
            logger.info("[MetaScheduler] Preparing hourly alert digest...")

            db = next(get_db())
            try:
                # Get high-priority alerts from last hour
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                alerts = db.query(MonitoringAlert).filter(
                    MonitoringAlert.created_at >= one_hour_ago,
                    MonitoringAlert.severity.in_(['high', 'medium']),
                    MonitoringAlert.status == 'open'
                ).order_by(MonitoringAlert.severity.desc(), MonitoringAlert.created_at.desc()).all()

                if not alerts:
                    logger.info("[MetaScheduler] No high-priority alerts in last hour, skipping digest")
                    return

                # Send digest
                success = await self.email_notifier.send_hourly_digest(alerts)

                if success:
                    logger.info(f"[MetaScheduler] ✓ Hourly digest sent: {len(alerts)} alerts")
                else:
                    logger.warning(f"[MetaScheduler] Failed to send hourly digest")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"[MetaScheduler] Error sending hourly digest: {e}", exc_info=True)

    async def _send_daily_health_report(self):
        """Send daily health report (9 AM)"""
        try:
            logger.info("[MetaScheduler] Preparing daily health report...")

            db = next(get_db())
            try:
                # Get latest evaluation results (from 3 AM run)
                from src.shared.models.meta_monitoring import MetaEvaluationRun
                latest_eval = db.query(MetaEvaluationRun).filter(
                    MetaEvaluationRun.run_type == 'daily',
                    MetaEvaluationRun.status == 'completed'
                ).order_by(MetaEvaluationRun.completed_at.desc()).first()

                # Get alerts from last 24 hours
                twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
                alerts_24h = db.query(MonitoringAlert).filter(
                    MonitoringAlert.created_at >= twenty_four_hours_ago
                ).order_by(MonitoringAlert.severity.desc(), MonitoringAlert.created_at.desc()).all()

                # Send daily digest
                success = await self.email_notifier.send_daily_digest(
                    evaluation_results=latest_eval,
                    alerts=alerts_24h
                )

                if success:
                    logger.info(
                        f"[MetaScheduler] ✓ Daily health report sent: "
                        f"{len(alerts_24h)} alerts in last 24h"
                    )
                else:
                    logger.warning("[MetaScheduler] Failed to send daily health report")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"[MetaScheduler] Error sending daily health report: {e}", exc_info=True)


# Global scheduler instance
_scheduler_instance = None


def get_scheduler() -> MetaMonitoringScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = MetaMonitoringScheduler()
    return _scheduler_instance


async def start_meta_monitoring():
    """Start the meta-monitoring scheduler (called at application startup)"""
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("[MetaScheduler] Meta-monitoring automation started")


async def stop_meta_monitoring():
    """Stop the meta-monitoring scheduler (called at application shutdown)"""
    scheduler = get_scheduler()
    scheduler.stop()
    logger.info("[MetaScheduler] Meta-monitoring automation stopped")


if __name__ == "__main__":
    # For testing the scheduler
    import asyncio

    async def test_scheduler():
        scheduler = get_scheduler()
        scheduler.start()

        print("\nScheduled Jobs:")
        print("-" * 60)
        for job in scheduler.get_jobs():
            print(f"• {job['name']}")
            print(f"  ID: {job['id']}")
            print(f"  Next Run: {job['next_run']}")
            print(f"  Trigger: {job['trigger']}")
            print()

        print("Scheduler is running. Press Ctrl+C to stop.\n")

        try:
            # Keep running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping scheduler...")
            scheduler.stop()

    asyncio.run(test_scheduler())
