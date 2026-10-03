from rest_framework import serializers

from .models import ClothRoll, DipRun, Loft, StretcherTag
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
    stretcherNo = serializers.SerializerMethodField()

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
            "stretcherNo",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "stretcherNo", "created_at", "updated_at")

    def get_stretcherNo(self, obj):
        # 视图已 prefetch stretcher_tags；遍历命中预取缓存，不产生逐卷查询
        for tag in obj.stretcher_tags.all():
            if tag.returned_at is None:
                return tag.stretcher_no
        return None

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
            if self.instance is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为浸渍中；请先建原布，再持绷架占用牌占架"}
                )
            # 仅在真正「进入浸渍中」时校验未归还牌；已在浸渍中则不拦台账编辑
            if self.instance.status != ClothRoll.STATUS_DIPPING:
                ok, msg = can_mark_roll_dipping(self.instance)
                if not ok:
                    raise serializers.ValidationError({"status": msg})
        elif new_status == ClothRoll.STATUS_CURED:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为已固化"}
                )
            # 固化只认最近浸渍时长满 12 小时，不掺占架规则
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


class StretcherTagSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    stretcherNo = serializers.IntegerField(
        source="stretcher_no",
        min_value=StretcherTag.MIN_STRETCHER_NO,
        max_value=StretcherTag.MAX_STRETCHER_NO,
    )
    holderId = serializers.IntegerField(source="holder_id", read_only=True)
    holderName = serializers.CharField(source="holder.username", read_only=True)
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)
    checkedOutAt = serializers.DateTimeField(source="checked_out_at", read_only=True)
    returnedAt = serializers.DateTimeField(source="returned_at", read_only=True)

    class Meta:
        model = StretcherTag
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "stretcherNo",
            "checkedOutAt",
            "returnedAt",
            "holderId",
            "holderName",
        )
        read_only_fields = (
            "id",
            "checkedOutAt",
            "returnedAt",
            "holderId",
            "holderName",
            "rollCode",
            "loftName",
        )
