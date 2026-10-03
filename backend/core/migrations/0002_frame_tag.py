import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FrameTag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("frame_no", models.PositiveSmallIntegerField()),
                ("occupied_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "occupied_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="frame_tags",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "roll",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="frame_tags",
                        to="core.clothroll",
                    ),
                ),
            ],
            options={
                "ordering": ["-occupied_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="frametag",
            constraint=models.CheckConstraint(
                check=models.Q(("frame_no__gte", 1), ("frame_no__lte", 99)),
                name="frame_tag_frame_no_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="frametag",
            constraint=models.UniqueConstraint(
                condition=models.Q(("returned_at__isnull", True)),
                fields=("frame_no",),
                name="uniq_open_frame_tag_per_frame",
            ),
        ),
        migrations.AddConstraint(
            model_name="frametag",
            constraint=models.UniqueConstraint(
                condition=models.Q(("returned_at__isnull", True)),
                fields=("roll",),
                name="uniq_open_frame_tag_per_roll",
            ),
        ),
    ]
