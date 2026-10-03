from django.conf import settings
from django.db import models
from django.utils import timezone


class Loft(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class ClothRoll(models.Model):
    STATUS_RAW = "raw"
    STATUS_DIPPING = "dipping"
    STATUS_CURED = "cured"
    STATUS_CHOICES = [
        (STATUS_RAW, "原布"),
        (STATUS_DIPPING, "浸渍中"),
        (STATUS_CURED, "已固化"),
    ]

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="rolls")
    roll_code = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RAW)
    fabric_weight_gsm = models.PositiveIntegerField(default=380)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loft_id", "roll_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["loft", "roll_code"],
                name="uniq_roll_code_per_loft",
            )
        ]

    def __str__(self):
        return f"{self.loft.name}/{self.roll_code}"


class DipRun(models.Model):
    roll = models.ForeignKey(ClothRoll, on_delete=models.CASCADE, related_name="dip_runs")
    started_at = models.DateTimeField()
    resin_pct = models.DecimalField(max_digits=5, decimal_places=2)
    cure_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Dip@{self.roll_id} {self.started_at}"


class FrameTag(models.Model):
    """绷架占用牌：布卷上绷架浸渍前须先占牌，归还后牌号才释放。"""

    FRAME_NO_MIN = 1
    FRAME_NO_MAX = 99

    roll = models.ForeignKey(ClothRoll, on_delete=models.CASCADE, related_name="frame_tags")
    frame_no = models.PositiveSmallIntegerField()
    occupied_at = models.DateTimeField(default=timezone.now)
    returned_at = models.DateTimeField(null=True, blank=True)
    occupied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="frame_tags",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occupied_at", "-id"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(frame_no__gte=1) & models.Q(frame_no__lte=99),
                name="frame_tag_frame_no_range",
            ),
            models.UniqueConstraint(
                fields=["frame_no"],
                condition=models.Q(returned_at__isnull=True),
                name="uniq_open_frame_tag_per_frame",
            ),
            models.UniqueConstraint(
                fields=["roll"],
                condition=models.Q(returned_at__isnull=True),
                name="uniq_open_frame_tag_per_roll",
            ),
        ]

    def __str__(self):
        state = "未归还" if self.returned_at is None else "已归还"
        return f"绷架{self.frame_no}号/{self.roll_id} ({state})"
