from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import ClothRoll, DipRun, FrameTag, Loft
from .rules import can_mark_roll_cured, can_mark_roll_dipping


class LoftSerializer(serializers.ModelSerializer):
    rollCount = serializers.SerializerMethodField()

    class Meta:
        model = Loft
        fields = ("id", "name", "location", "notes", "rollCount", "created_at")
        read_only_fields = ("id", "rollCount", "created_at")

    def get_rollCount(self, obj):
        if hasattr(obj, "roll_count"):
            return obj.roll_count
        return obj.rolls.count()


class ClothRollSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    rollCode = serializers.CharField(source="roll_code")
    fabricWeightGsm = serializers.IntegerField(source="fabric_weight_gsm", required=False)
    loftName = serializers.CharField(source="loft.name", read_only=True)

    class Meta:
        model = ClothRoll
        fields = (
            "id",
            "loftId",
            "loftName",
            "rollCode",
            "status",
            "fabricWeightGsm",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "created_at", "updated_at")

    def validate(self, attrs):
        loft = attrs.get("loft") or getattr(self.instance, "loft", None)
        roll_code = attrs.get("roll_code") or getattr(self.instance, "roll_code", None)
        if loft and roll_code:
            qs = ClothRoll.objects.filter(loft=loft, roll_code=roll_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"rollCode": "同一帆布间卷号必须唯一"})

        new_status = attrs.get("status")
        if new_status == ClothRoll.STATUS_DIPPING:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "该布卷没有未归还的绷架占用牌，不能标记为浸渍中"}
                )
            if roll.status != ClothRoll.STATUS_DIPPING:
                ok, msg = can_mark_roll_dipping(roll)
                if not ok:
                    raise serializers.ValidationError({"status": msg})
        if new_status == ClothRoll.STATUS_CURED:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为已固化"}
                )
            # 合并未提交字段到临时视角：用当前实例校验
            ok, msg = can_mark_roll_cured(roll)
            if not ok:
                raise serializers.ValidationError({"status": msg})
        return attrs


class DipRunSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    startedAt = serializers.DateTimeField(source="started_at")
    resinPct = serializers.DecimalField(source="resin_pct", max_digits=5, decimal_places=2)
    cureHours = serializers.DecimalField(
        source="cure_hours",
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)

    class Meta:
        model = DipRun
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "startedAt",
            "resinPct",
            "cureHours",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "rollCode", "loftName", "created_at")


class FrameTagSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    frameNo = serializers.IntegerField(
        source="frame_no",
        min_value=FrameTag.FRAME_NO_MIN,
        max_value=FrameTag.FRAME_NO_MAX,
        error_messages={
            "min_value": "绷架号须为 1 到 99 的整数",
            "max_value": "绷架号须为 1 到 99 的整数",
            "invalid": "绷架号须为 1 到 99 的整数",
        },
    )
    occupiedAt = serializers.DateTimeField(source="occupied_at", read_only=True)
    returnedAt = serializers.DateTimeField(source="returned_at", read_only=True)
    occupiedBy = serializers.IntegerField(source="occupied_by.id", read_only=True)
    occupiedByName = serializers.CharField(source="occupied_by.username", read_only=True)
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)

    class Meta:
        model = FrameTag
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "frameNo",
            "occupiedAt",
            "returnedAt",
            "occupiedBy",
            "occupiedByName",
            "created_at",
        )
        read_only_fields = (
            "id",
            "rollCode",
            "loftName",
            "occupiedAt",
            "returnedAt",
            "occupiedBy",
            "occupiedByName",
            "created_at",
        )

    def validate(self, attrs):
        roll = attrs.get("roll")
        frame_no = attrs.get("frame_no")
        if roll is not None and roll.status == ClothRoll.STATUS_CURED:
            raise serializers.ValidationError(
                {"rollId": "已固化布卷禁止新占绷架"}
            )
        if roll is not None and roll.frame_tags.filter(returned_at__isnull=True).exists():
            raise serializers.ValidationError(
                {"rollId": "该布卷已有未归还的绷架占用牌，须先归还"}
            )
        if frame_no is not None and FrameTag.objects.filter(
            frame_no=frame_no, returned_at__isnull=True
        ).exists():
            raise serializers.ValidationError(
                {"frameNo": f"绷架 {frame_no} 号正被其他布卷占用，尚未归还"}
            )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["occupied_by"] = request.user
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            # 并发占架撞号：数据库唯一约束兜底，转成可读中文错误
            frame_no = validated_data.get("frame_no")
            roll = validated_data.get("roll")
            if FrameTag.objects.filter(
                frame_no=frame_no, returned_at__isnull=True
            ).exists():
                raise serializers.ValidationError(
                    {"frameNo": f"绷架 {frame_no} 号正被其他布卷占用，尚未归还"}
                )
            if roll is not None:
                raise serializers.ValidationError(
                    {"rollId": "该布卷已有未归还的绷架占用牌，须先归还"}
                )
            raise
