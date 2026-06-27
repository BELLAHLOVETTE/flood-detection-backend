# apps/alerts/tasks.py
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def dispatch_alert_to_subscribers(alert_id):
    """
    Send a FloodAlert to all active, verified subscribers via email.
    Synchronous — runs inside the request. No Celery worker needed.
    Returns a dict with counts for the API response.
    """
    from apps.alerts.models import FloodAlert, AlertSubscriber, AlertDelivery

    try:
        alert = FloodAlert.objects.get(id=alert_id)
    except FloodAlert.DoesNotExist:
        logger.error(f"FloodAlert {alert_id} not found")
        return {'email_sent': 0, 'sms_sent': 0, 'total': 0, 'error': 'alert_not_found'}

    # Only active, verified subscribers who want email or both
    subscribers = AlertSubscriber.objects.filter(
        is_active=True,
        is_verified=True,
        preferred_channel__in=['email', 'both'],
    ).exclude(email='').exclude(email__isnull=True)

    email_sent_count = 0
    total = subscribers.count()

    for sub in subscribers:
        # Pick the message in the subscriber's language, fall back to FR
        if sub.language == 'en' and alert.message_en:
            body = alert.message_en
        else:
            body = alert.message_fr or alert.message_en or alert.title

        subject = f"[Flood-Watch] {alert.title}"

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[sub.email],
                fail_silently=False,
            )
            status = 'sent'
            email_sent_count += 1
        except Exception as e:
            logger.error(f"Email failed for subscriber {sub.id}: {e}")
            status = 'failed'

        # Record the delivery attempt
        try:
            AlertDelivery.objects.update_or_create(
                alert=alert,
                subscriber=sub,
                channel='email',
                defaults={'status': status},
            )
        except Exception as e:
            logger.warning(f"Could not record delivery for subscriber {sub.id}: {e}")

    # Update the alert's sent counters
    alert.email_sent = email_sent_count
    alert.total_recipients = total
    alert.save(update_fields=['email_sent', 'total_recipients'])

    logger.info(f"Alert {alert_id} dispatched: {email_sent_count}/{total} emails sent")

    return {
        'email_sent': email_sent_count,
        'sms_sent':   0,  # SMS parked until Twilio resolves
        'total':      total,
    }