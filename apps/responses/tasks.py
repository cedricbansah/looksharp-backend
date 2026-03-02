import logging

from celery import shared_task
from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue="critical",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def apply_side_effects(self, survey_id: str, user_id: str) -> None:
    """
    Idempotent task: award points and increment counters after a survey response.

    Mirrors the logic of response-count-function/main.py _process_response().
    Uses select_for_update() for row-level locking (Postgres equivalent of
    a Firestore transaction).
    """
    from apps.surveys.models import Survey
    from apps.users.models import User

    with transaction.atomic():
        try:
            survey = Survey.objects.select_for_update().get(id=survey_id)
        except Survey.DoesNotExist:
            logger.warning("Survey %s not found - skipping reward", survey_id)
            return

        try:
            user = User.objects.select_for_update().get(id=user_id)
        except User.DoesNotExist:
            logger.warning("User %s not found - skipping reward", user_id)
            return

        # Idempotency guard - mirrors surveys_completed check in the Cloud Function
        if survey_id in (user.surveys_completed or []):
            logger.info(
                "Duplicate reward skipped: user %s already completed survey %s",
                user_id,
                survey_id,
            )
            return

        points = survey.points if isinstance(survey.points, int) else 0

        # Atomic increment - equivalent of Firestore Increment + ArrayUnion
        Survey.objects.filter(id=survey_id).update(response_count=F("response_count") + 1)
        User.objects.filter(id=user_id).update(
            points=F("points") + points,
            surveys_completed=user.surveys_completed + [survey_id],
        )

        logger.info(
            "Reward applied: survey=%s user=%s points=%s",
            survey_id,
            user_id,
            points,
        )
