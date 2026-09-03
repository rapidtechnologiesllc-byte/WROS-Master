"""
Weekly Performers Email Service

Auto-sends motivational emails every Friday at 8 AM IST to the entire org.
- Top performers get celebration emails
- Bottom performers get motivation/improvement emails
- Creates healthy competition and accountability
"""

from datetime import datetime, timedelta
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.candidate import Candidate
from app.models.user import User
from app.core.logging import logger
from app.services.email_service import send_email
import logging

def calculate_weekly_performance(db: Session) -> List[Tuple[dict, int]]:
    """
    Calculate performance metrics for all recruiters this week.

    Returns: List of (user_dict, score) tuples sorted by score descending
    """
    # Get start of current week (Monday) and end (Friday)
    today = datetime.utcnow().date()
    days_since_monday = today.weekday()
    week_start = today - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=4)  # Friday

    # Query all recruiters with their candidates added this week
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(week_end, datetime.max.time())

    recruiters = db.query(User).filter(
        User.user_active == True,
        User.user_role.in_(["HR Manager", "Recruiter", "Hiring Manager"])
    ).all()

    performance = []

    for recruiter in recruiters:
        # Count candidates added this week
        candidates_added = db.query(Candidate).filter(
            Candidate.assigned_hr_manager_id == recruiter.user_id,
            Candidate.created_at >= week_start_dt,
            Candidate.created_at <= week_end_dt
        ).count()

        # Count offers this week
        offers_made = db.query(Candidate).filter(
            Candidate.assigned_hr_manager_id == recruiter.user_id,
            Candidate.candidate_status == "Offer Extended",
            Candidate.updated_at >= week_start_dt,
            Candidate.updated_at <= week_end_dt
        ).count()

        # Count interviews scheduled this week
        interviews_scheduled = db.query(Candidate).filter(
            Candidate.assigned_hr_manager_id == recruiter.user_id,
            Candidate.candidate_status == "Interview Scheduled",
            Candidate.updated_at >= week_start_dt,
            Candidate.updated_at <= week_end_dt
        ).count()

        # Calculate score: candidates (+1), offers (+2), interviews (+1)
        score = candidates_added + (offers_made * 2) + interviews_scheduled

        recruiter_data = {
            "user_id": str(recruiter.user_id),
            "name": recruiter.user_name or "Unknown Recruiter",
            "email": recruiter.user_email,
            "candidates_added": candidates_added,
            "offers_made": offers_made,
            "interviews_scheduled": interviews_scheduled,
        }

        performance.append((recruiter_data, score))

    # Sort by score descending
    performance.sort(key=lambda x: x[1], reverse=True)

    return performance

def send_top_performer_email(performer: dict, rank: int, score: int):
    """Send celebration email to top performer."""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    medal = medals.get(rank, "⭐")

    subject = f"{medal} You're a Top Performer! Week of {datetime.utcnow().strftime('%b %d')}"

    body = f"""
    <h2>🎉 Congratulations, {performer['name']}!</h2>

    <p>You're ranked <strong>#{rank}</strong> this week in our org-wide performance rankings!</p>

    <h3>Your Weekly Stats:</h3>
    <ul>
        <li><strong>{performer['candidates_added']}</strong> candidates added</li>
        <li><strong>{performer['offers_made']}</strong> offers made</li>
        <li><strong>{performer['interviews_scheduled']}</strong> interviews scheduled</li>
        <li><strong>Score: {score} points</strong></li>
    </ul>

    <p>Keep up the amazing work! Your effort drives our organization's success. 🚀</p>

    <p style="font-size: 12px; color: #666;">
        This is an automated weekly performance email sent every Friday at 8 AM IST.
    </p>
    """

    try:
        send_email(
            to_email=performer['email'],
            subject=subject,
            html_content=body
        )
        logger.info(f"Sent top performer email to {performer['name']} ({performer['email']})")
    except Exception as e:
        logger.error(f"Failed to send top performer email to {performer['email']}: {e}")

def send_improvement_email(performer: dict, rank: int, total_recruiters: int, score: int):
    """Send motivational email to bottom performer with improvement tips."""

    subject = f"📈 Let's Improve Together! Your Weekly Performance Summary"

    body = f"""
    <h2>Hi {performer['name']},</h2>

    <p>Here's your weekly performance summary and some friendly motivation to help you reach new heights! 💪</p>

    <h3>Your Weekly Stats:</h3>
    <ul>
        <li><strong>{performer['candidates_added']}</strong> candidates added</li>
        <li><strong>{performer['offers_made']}</strong> offers made</li>
        <li><strong>{performer['interviews_scheduled']}</strong> interviews scheduled</li>
        <li><strong>Score: {score} points</strong></li>
    </ul>

    <p>You're currently ranked <strong>#{rank} out of {total_recruiters}</strong> in our organization.</p>

    <h3>💡 Tips to Improve:</h3>
    <ul>
        <li>✅ Queue more LinkedIn candidates (use LinkedIn Pipeline tool)</li>
        <li>✅ Follow up on pending connections</li>
        <li>✅ Focus on getting offers in front of top candidates</li>
        <li>✅ Schedule more interviews with interested candidates</li>
    </ul>

    <p>Remember: Every great recruiter started somewhere. You've got this! Let's crush it next week. 🎯</p>

    <p style="font-size: 12px; color: #666;">
        This is an automated weekly performance email sent every Friday at 8 AM IST.
        Questions? Reach out to your manager or the HR team.
    </p>
    """

    try:
        send_email(
            to_email=performer['email'],
            subject=subject,
            html_content=body
        )
        logger.info(f"Sent improvement email to {performer['name']} ({performer['email']})")
    except Exception as e:
        logger.error(f"Failed to send improvement email to {performer['email']}: {e}")

def send_weekly_performers_email(db: Session):
    """
    Main function: Calculate performance and send emails to entire org.

    Called by APScheduler every Friday at 8 AM IST.
    """
    try:
        logger.info("Starting weekly performers email send...")

        # Calculate performance
        performance = calculate_weekly_performance(db)

        if not performance:
            logger.info("No performers found for this week")
            return

        total_count = len(performance)

        # Send emails to top 3 (celebration)
        for rank, (performer, score) in enumerate(performance[:3], 1):
            send_top_performer_email(performer, rank, score)

        # Send emails to bottom 3 (motivation to improve)
        if total_count > 3:
            for performer, score in performance[-3:]:
                rank = performance.index((performer, score)) + 1
                send_improvement_email(performer, rank, total_count, score)

        logger.info(f"Weekly performers email send complete. Sent to {min(6, total_count)} users.")

    except Exception as e:
        logger.error(f"Failed to send weekly performers emails: {e}", exc_info=True)

def schedule_weekly_performers_email():
    """
    Schedule the weekly performers email to send every Friday at 8 AM IST.

    Called during application startup.
    """
    from app.core.scheduler import scheduler
    from pytz import timezone

    try:
        ist = timezone('Asia/Kolkata')

        scheduler.add_job(
            func=lambda: send_weekly_performers_email(db=None),  # DB will be created in job
            trigger="cron",
            day_of_week="fri",  # Friday
            hour=8,  # 8 AM
            minute=0,
            second=0,
            timezone=ist,
            id="weekly_performers_email",
            name="Weekly Performers Email",
            replace_existing=True
        )

        logger.info("✅ Weekly performers email scheduled for Friday 8 AM IST")

    except Exception as e:
        logger.error(f"Failed to schedule weekly performers email: {e}", exc_info=True)
