from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, Loft, StretcherTag
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    StretcherTagSerializer,
)


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        # prefetch 供 stretcherNo 字段批量读取未归还牌，避免逐卷查询
        qs = ClothRoll.objects.select_related("loft").prefetch_related(
            "stretcher_tags"
        ).all()
        loft_id = self.request.query_params.get("loftId")
        status_filter = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs


class StretcherTagViewSet(viewsets.ModelViewSet):
    serializer_class = StretcherTagSerializer
    permission_classes = [IsAuthenticated]
    # 只允许查、占出（POST 集合）与归还（POST 动作）；不得 PATCH/DELETE 绕过规则
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = StretcherTag.objects.select_related("roll", "roll__loft", "holder").all()
        if self.request.query_params.get("open") == "1":
            qs = qs.filter(returned_at__isnull=True)
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs

    def _blocked_create(self, msg, code=status.HTTP_400_BAD_REQUEST):
        return Response({"detail": msg}, status=code)

    def create(self, request, *args, **kwargs):
        """占架：操作工凭未归还牌占用一个绷架号。"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roll = serializer.validated_data["roll"]
        stretcher_no = serializer.validated_data["stretcher_no"]

        if roll.status == ClothRoll.STATUS_CURED:
            return self._blocked_create("该卷已固化，禁止新占绷架")

        if StretcherTag.objects.filter(
            roll=roll, returned_at__isnull=True
        ).exists():
            return self._blocked_create("该卷已有未归还占用牌，不能重复占架")

        busy = StretcherTag.objects.filter(
            stretcher_no=stretcher_no, returned_at__isnull=True
        ).values_list("roll__roll_code", flat=True).first()
        if busy is not None:
            return self._blocked_create(
                f"{stretcher_no} 号绷架正被布卷 {busy} 占用，未归还前不能再占"
            )

        tag = StretcherTag(roll=roll, stretcher_no=stretcher_no, holder=request.user)
        try:
            # 两名浸胶工抢同一架号时，数据库部分唯一索引只放行一卷
            with transaction.atomic():
                tag.save()
        except IntegrityError:
            return self._blocked_create(
                f"{stretcher_no} 号绷架刚被他人占用，请改占其他绷架号",
                code=status.HTTP_409_CONFLICT,
            )
        out = self.get_serializer(tag)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def return_tag(self, request, pk=None):
        """归还：把未归还牌归还（归还时刻置为当前）。"""
        tag = self.get_object()
        if tag.returned_at is not None:
            return Response(
                {"detail": "该牌已归还，无需重复归还"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tag.returned_at = timezone.now()
        tag.save(update_fields=["returned_at"])
        return Response(self.get_serializer(tag).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
        "openStretcherCount": StretcherTag.objects.filter(
            returned_at__isnull=True
        ).count(),
    }
    return Response(data)
