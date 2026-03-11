from django.db import migrations, models
import django.db.models.deletion


def _backfill_survey_client_fk(apps, schema_editor):
    Survey = apps.get_model("surveys", "Survey")
    Client = apps.get_model("clients", "Client")

    client_ids = set(Client.objects.values_list("id", flat=True))
    updates = []
    for survey in Survey.objects.exclude(client_legacy_id=""):
        legacy_id = survey.client_legacy_id
        if legacy_id and legacy_id in client_ids:
            survey.client_id = legacy_id
            updates.append(survey)

    if updates:
        Survey.objects.bulk_update(updates, ["client"])


def _restore_survey_legacy_client_id(apps, schema_editor):
    Survey = apps.get_model("surveys", "Survey")

    updates = []
    for survey in Survey.objects.exclude(client_id__isnull=True):
        survey.client_legacy_id = survey.client_id
        updates.append(survey)

    if updates:
        Survey.objects.bulk_update(updates, ["client_legacy_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0003_alter_client_logo_url_alter_client_website_url"),
        ("surveys", "0004_remove_question_questions_survey__8f7497_idx_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="survey",
            old_name="client_id",
            new_name="client_legacy_id",
        ),
        migrations.AddField(
            model_name="survey",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="surveys",
                to="clients.client",
            ),
        ),
        migrations.RunPython(_backfill_survey_client_fk, _restore_survey_legacy_client_id),
        migrations.RemoveField(
            model_name="survey",
            name="client_name",
        ),
        migrations.RemoveField(
            model_name="survey",
            name="client_legacy_id",
        ),
    ]
