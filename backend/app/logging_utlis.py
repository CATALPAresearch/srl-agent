import hashlib
import os
import time
import uuid
from flask import request, has_request_context
from app import db
from .actions import LogAction
from .models import ActivityLog
import logging


def _hash_ip(ip: str) -> str:
    """One-way hash of IP address using a server-side salt for pseudonymisation.
    Same IP always yields the same hash (linkable), but the original cannot be recovered."""
    salt = os.environ.get("SECRET_KEY", "fallback_secret_key")
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:16]


logger = logging.getLogger("InterviewAgent")


def log_action(
        action: LogAction,
        user=None,
        value=None,
        context=None,
        strategy=None,
        turn=None,
        step=None,
        http_status=None,
        user_agent=None,
        include_ip=True
):
    """
    Central logging function for all activity in the system.

    Args:
        action (LogAction): The action being performed
        user (User): User object
        value (dict): Additional data as JSON
        context (str): Context
        strategy (str): Strategy
        turn (int): Conversation turn
        step (str): Conversation step
        http_status (int): HTTP status code
        user_agent (str): Override user agent
        include_ip (bool): Whether to store the client IP address

    Example:
        log_action(
            LogAction.START_CONVERSATION,
            user=user,
            value={"language": "en"},
            http_status=200
        )
    """
    try:
        extracted_user_agent = None
        ip = None

        if has_request_context():
            extracted_user_agent = user_agent or request.headers.get('User-Agent')

            # behind nginx, remote_addr is the proxy; X-Real-IP carries the client address
            client_ip = request.headers.get("X-Real-IP") or request.remote_addr
            if include_ip and client_ip:
                ip = _hash_ip(client_ip)

        log_entry = ActivityLog(
            id=str(uuid.uuid4()),
            timestamp=int(time.time()),
            user_id=user.id if user else None,
            user_client=user.client if user else None,
            action=action.value,
            value=value,
            user_agent=extracted_user_agent,
            ip_address=ip,
            context=context,
            strategy=strategy,
            turn=turn,
            step=step,
            http_status=http_status
        )

        db.session.add(log_entry)
        db.session.commit()

        logger.debug("Logged action: %s for user %s", action.value, user.id if user else "system")
        return log_entry

    except Exception as e:
        db.session.rollback()
        logger.error("Failed to log action %s: %s", action, e)
        return None
