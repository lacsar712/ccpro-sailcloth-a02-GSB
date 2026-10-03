"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from .models import ClothRoll, DipRun, FrameTag

MIN_CURE_HOURS_FOR_CURED = Decimal("12")


def latest_dip_run(roll: ClothRoll) -> DipRun | None:
    return roll.dip_runs.order_by("-started_at", "-id").first()


def open_frame_tag(roll: ClothRoll) -> FrameTag | None:
    """该卷当前未归还的绷架占用牌（每卷至多一张，由数据库约束保证）。"""
    return (
        roll.frame_tags.filter(returned_at__isnull=True)
        .order_by("-occupied_at", "-id")
        .first()
    )


def can_mark_roll_dipping(roll: ClothRoll) -> tuple[bool, str]:
    """
    布卷转为「浸渍中」(dipping) 的前提：
    该卷须持有一张未归还的绷架占用牌。
    """
    if open_frame_tag(roll) is None:
        return False, "该布卷没有未归还的绷架占用牌，不能标记为浸渍中"
    return True, ""


def can_mark_roll_cured(roll: ClothRoll) -> tuple[bool, str]:
    """
    布卷转为「已固化」(cured) 的前提：
    最近一条浸渍记录的固化时长已记录，且 >= 12 小时。
    """
    latest = latest_dip_run(roll)
    if latest is None:
        return False, "该布卷尚无浸渍记录，不能标记为已固化"
    if latest.cure_hours is None:
        return False, "最近浸渍记录尚未填写固化时长，不能标记为已固化"
    if latest.cure_hours < MIN_CURE_HOURS_FOR_CURED:
        return (
            False,
            f"最近浸渍固化时长 {latest.cure_hours} 小时低于 {MIN_CURE_HOURS_FOR_CURED} 小时，不能标记为已固化",
        )
    return True, ""
