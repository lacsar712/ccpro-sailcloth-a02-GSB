from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, FrameTag, Loft
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    FrameTagSerializer,
    LoftSerializer,
)


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft").all()
        loft_id = self.request.query_params.get("loftId")
        status = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status:
            qs = qs.filter(status=status)
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


class FrameTagViewSet(viewsets.ModelViewSet):
    """绷架占用牌：操作工登录后即可占架与归还。"""

    serializer_class = FrameTagSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = FrameTag.objects.select_related("roll", "roll__loft", "occupied_by").all()
        open_only = self.request.query_params.get("open")
        if open_only in ("1", "true", "yes"):
            qs = qs.filter(returned_at__isnull=True)
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs

    @action(detail=True, methods=["post"], url_path="return", url_name="return")
    def return_tag(self, request, pk=None):
        tag = self.get_object()
        updated = FrameTag.objects.filter(
            pk=tag.pk, returned_at__isnull=True
        ).update(returned_at=timezone.now())
        if not updated:
            return Response(
                {"detail": "该绷架占用牌已归还，不能重复归还"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tag.refresh_from_db()
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
    }
    return Response(data)
