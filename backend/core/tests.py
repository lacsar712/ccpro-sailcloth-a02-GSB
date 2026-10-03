from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from core.models import ClothRoll, DipRun, Loft, StretcherTag

User = get_user_model()


class StretcherRuleTests(TestCase):
    def setUp(self):
        self.loft = Loft.objects.create(name="北岸帆布间", location="港区二号库")
        self.w1 = User.objects.create_user(username="gum1", password="x", role="worker")
        self.w2 = User.objects.create_user(username="gum2", password="x", role="worker")
        self.client = APIClient()
        self.client.force_authenticate(self.w1)
        self.client2 = APIClient()
        self.client2.force_authenticate(self.w2)

    def _roll(self, code="R-01", status=ClothRoll.STATUS_RAW):
        return ClothRoll.objects.create(
            loft=self.loft, roll_code=code, status=status
        )

    def _checkout(self, client, roll_id, stretcher_no):
        return client.post(
            "/api/stretcher-tags/",
            {"rollId": roll_id, "stretcherNo": stretcher_no},
            format="json",
        )

    # ---- 种子 ----

    def test_seed_one_raw_roll_zero_tags(self):
        Loft.objects.all().delete()
        call_command("seed_data")
        self.assertEqual(ClothRoll.objects.count(), 1)
        self.assertEqual(ClothRoll.objects.get().status, ClothRoll.STATUS_RAW)
        self.assertEqual(StretcherTag.objects.count(), 0)

    # ---- 无牌不得改浸渍中 ----

    def test_raw_cannot_become_dipping_without_open_tag(self):
        roll = self._roll()
        res = self.client.patch(f"/api/rolls/{roll.id}/", {"status": "dipping"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("绷架", res.data["status"][0])

    def test_dipping_blocked_on_ledger_create_too(self):
        # 建卷直接带 dipping 同样挡住
        res = self.client.post(
            "/api/rolls/",
            {"loftId": self.loft.id, "rollCode": "RX", "status": "dipping"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("绷架", str(res.data))

    def test_raw_can_become_dipping_with_open_tag(self):
        roll = self._roll()
        res = self._checkout(self.client, roll.id, 7)
        self.assertEqual(res.status_code, 201)
        res = self.client.patch(f"/api/rolls/{roll.id}/", {"status": "dipping"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "dipping")
        self.assertEqual(res.data["stretcherNo"], 7)

    # ---- 占架 ----

    def test_checkout_basic_fields(self):
        roll = self._roll()
        res = self._checkout(self.client, roll.id, 42)
        self.assertEqual(res.status_code, 201)
        data = res.data
        self.assertEqual(data["stretcherNo"], 42)
        self.assertEqual(data["rollId"], roll.id)
        self.assertEqual(data["holderName"], "gum1")
        self.assertIsNotNone(data["checkedOutAt"])
        self.assertIsNone(data["returnedAt"])

    def test_stretcher_no_bounds(self):
        roll = self._roll()
        for bad in (0, 100, -1):
            res = self._checkout(self.client, roll.id, bad)
            self.assertEqual(res.status_code, 400, msg=bad)

    def test_same_stretcher_second_roll_blocked(self):
        a = self._roll("A")
        b = self._roll("B")
        self.assertEqual(self._checkout(self.client, a.id, 5).status_code, 201)
        res = self._checkout(self.client2, b.id, 5)
        self.assertEqual(res.status_code, 400)
        self.assertIn("绷架", res.data["detail"])
        # 只许一卷成功
        self.assertEqual(
            StretcherTag.objects.filter(
                stretcher_no=5, returned_at__isnull=True
            ).count(),
            1,
        )

    def test_same_roll_only_one_open_tag(self):
        a = self._roll("A")
        self.assertEqual(self._checkout(self.client, a.id, 1).status_code, 201)
        res = self._checkout(self.client2, a.id, 2)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            StretcherTag.objects.filter(roll=a, returned_at__isnull=True).count(), 1
        )

    def test_cured_roll_cannot_checkout(self):
        roll = self._roll(status=ClothRoll.STATUS_CURED)
        res = self._checkout(self.client, roll.id, 3)
        self.assertEqual(res.status_code, 400)
        self.assertIn("固化", res.data["detail"])

    def test_db_constraints_block_double_occupancy(self):
        # 数据库层兜底：模拟两卷同时写入同一架号
        a = self._roll("A")
        b = self._roll("B")
        StretcherTag.objects.create(roll=a, stretcher_no=9, holder=self.w1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StretcherTag.objects.create(roll=b, stretcher_no=9, holder=self.w2)
        # 同一卷两张未归还牌同样被数据库拒绝
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StretcherTag.objects.create(roll=a, stretcher_no=10, holder=self.w1)

    def test_checkout_race_returns_409(self):
        # 两请求预检都看到架号空闲、插入时撞唯一索引 -> 409 中文挡住
        a = self._roll("A")
        b = self._roll("B")
        StretcherTag.objects.create(roll=a, stretcher_no=11, holder=self.w1)

        with mock.patch(
            "core.views.StretcherTag.objects.filter",
            return_value=mock.MagicMock(
                **{
                    "exists.return_value": False,
                    "values_list.return_value.first.return_value": None,
                }
            ),
        ):
            res = self.client.post(
                "/api/stretcher-tags/",
                {"rollId": b.id, "stretcherNo": 11},
                format="json",
            )
        self.assertEqual(res.status_code, 409)
        self.assertIn("占用", res.data["detail"])
        self.assertEqual(
            StretcherTag.objects.filter(
                stretcher_no=11, returned_at__isnull=True
            ).count(),
            1,
        )

    # ---- 归还 ----

    def test_return_frees_stretcher(self):
        a = self._roll("A")
        tag = self._checkout(self.client, a.id, 8).data
        res = self.client.post(f"/api/stretcher-tags/{tag['id']}/return_tag/")
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.data["returnedAt"])

        b = self._roll("B")
        res = self._checkout(self.client2, b.id, 8)
        self.assertEqual(res.status_code, 201)

    def test_double_return_blocked(self):
        a = self._roll("A")
        tag = self._checkout(self.client, a.id, 8).data
        self.client.post(f"/api/stretcher-tags/{tag['id']}/return_tag/")
        res = self.client.post(f"/api/stretcher-tags/{tag['id']}/return_tag/")
        self.assertEqual(res.status_code, 400)

    def test_open_list_filter(self):
        a = self._roll("A")
        tag = self._checkout(self.client, a.id, 8).data
        self.client.post(f"/api/stretcher-tags/{tag['id']}/return_tag/")
        open_res = self.client.get("/api/stretcher-tags/?open=1")
        self.assertEqual(open_res.data["count"] if isinstance(open_res.data, dict) else len(open_res.data), 0)

    # ---- 固化判断不掺占架 ----

    def _add_dip(self, roll, hours, when=None):
        DipRun.objects.create(
            roll=roll,
            started_at=when or timezone.now(),
            resin_pct=Decimal("28.0"),
            cure_hours=Decimal(str(hours)),
        )

    def test_cure_only_cares_about_cure_hours_not_tag(self):
        roll = self._roll(status=ClothRoll.STATUS_DIPPING)
        # 有牌但时长不足：仍被固化规则挡住
        self._checkout(self.client, roll.id, 6)
        self._add_dip(roll, "10.00")
        res = self.client.patch(f"/api/rolls/{roll.id}/", {"status": "cured"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("12", res.data["status"][0])

        # 牌已归还（无未归还牌）但时长满 12：允许固化，占架不参与判断
        tag = StretcherTag.objects.get(roll=roll)
        tag.returned_at = timezone.now()
        tag.save()
        self._add_dip(roll, "14.00", when=timezone.now() + timedelta(hours=1))
        res = self.client.patch(f"/api/rolls/{roll.id}/", {"status": "cured"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "cured")

    def test_dipping_roll_edit_other_fields_without_tag_ok(self):
        # 已在浸渍中的卷做台账编辑不应再被占架规则拦
        roll = self._roll(status=ClothRoll.STATUS_DIPPING)
        res = self.client.patch(f"/api/rolls/{roll.id}/", {"notes": "备注"}, format="json")
        self.assertEqual(res.status_code, 200)
