# Generated manually for Phase 3

from django.db import migrations, models

import apps.surveys.models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="survey",
            name="category",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="survey",
            name="client_id",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="survey",
            name="client_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="survey",
            name="created_by",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="survey",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="survey",
            name="end_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="survey",
            name="estimated_time",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="survey",
            name="question_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="survey",
            name="status",
            field=models.CharField(
                choices=[("draft", "Draft"), ("active", "Active"), ("completed", "Completed")],
                default="draft",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                ("id", models.CharField(default=apps.surveys.models._question_id, max_length=128, primary_key=True, serialize=False)),
                ("question_text", models.CharField(max_length=500)),
                ("question_subtext", models.CharField(blank=True, max_length=200)),
                (
                    "question_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("single_select", "Single Select"),
                            ("multi_select", "Multi Select"),
                            ("single_select_other", "Single Select Other"),
                            ("multi_select_other", "Multi Select Other"),
                            ("linear_scale", "Linear Scale"),
                        ],
                        default="text",
                        max_length=32,
                    ),
                ),
                ("position_index", models.PositiveIntegerField(default=0)),
                ("choices", models.JSONField(blank=True, default=list)),
                ("scale_lower_limit", models.IntegerField(blank=True, null=True)),
                ("scale_upper_limit", models.IntegerField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "survey",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="questions", to="surveys.survey"),
                ),
            ],
            options={
                "db_table": "questions",
            },
        ),
        migrations.AddIndex(
            model_name="survey",
            index=models.Index(fields=["is_deleted", "status", "-created_at"], name="surveys_surv_is_dele_03c888_idx"),
        ),
        migrations.AddIndex(
            model_name="survey",
            index=models.Index(fields=["is_deleted", "category", "-created_at"], name="surveys_surv_is_dele_6e16e8_idx"),
        ),
        migrations.AddIndex(
            model_name="question",
            index=models.Index(fields=["survey", "is_deleted", "position_index"], name="questions_qu_survey__f6b26f_idx"),
        ),
    ]
