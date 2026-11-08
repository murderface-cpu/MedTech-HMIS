import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.departments import models as DepartmentModels
from apps.manager.access import INVENTORY, PHARMACY
from apps.manager.testing import make_drug, make_user
from apps.stores import models as StoreModels


class StoresAccessTest(TestCase):
    def test_store_pages_need_inventory(self):
        self.client.force_login(make_user("pharm", modules=[PHARMACY]))
        for name in ("adjustments", "purchase-orders"):
            self.assertEqual(self.client.get(reverse(f"stores:{name}")).status_code, 403, name)
        # departments raise requisitions to the store
        self.assertEqual(self.client.get(reverse("stores:requisitions")).status_code, 200)


class StockAdjustmentTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("store", modules=[INVENTORY]))
        self.drug = make_drug(stock=100, expiry=timezone.localdate() + datetime.timedelta(days=300))
        self.batch = DepartmentModels.StockBatch.objects.get(drug=self.drug)
        self.batch.quantity_remaining = 100
        self.batch.save()

    def test_count_sets_the_batch_and_records_the_difference(self):
        self.client.post(reverse("stores:adjustments"), {
            "intent": "adjust", "adjustment-batch": self.batch.pk, "adjustment-counted": 92, "adjustment-reason": "count"})
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity_remaining, 92)
        adjustment = StoreModels.StockAdjustment.objects.get()
        self.assertEqual((adjustment.quantity_before, adjustment.quantity_change), (100, -8))

    def test_cannot_take_more_than_the_batch_holds(self):
        with self.assertRaises(ValueError):
            StoreModels.StockAdjustment.apply(self.batch, -101, "lost", None)


class PurchaseOrderTest(TestCase):
    def test_receiving_creates_stock_and_closes_the_order(self):
        user = make_user("store", modules=[INVENTORY])
        drug = make_drug()
        supplier = DepartmentModels.Supplier.objects.create(name="MEDS")
        order = StoreModels.PurchaseOrder.objects.create(supplier=supplier, status="sent", created_by=user)
        line = StoreModels.PurchaseOrderLine.objects.create(order=order, drug=drug, quantity_ordered=50, unit_cost=3)
        line.quantity_received = 50
        line.save()
        order.refresh_status()
        self.assertEqual(order.status, "received")
