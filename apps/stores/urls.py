from django.urls import path

from apps.stores import views

app_name = "stores"

urlpatterns = [
    path("inventory/adjustments/", views.StockAdjustmentsView.as_view(), name="adjustments"),
    path("inventory/purchase-orders/", views.PurchaseOrdersView.as_view(), name="purchase-orders"),
    path("inventory/purchase-orders/<int:pk>/", views.PurchaseOrderDetailView.as_view(), name="purchase-order"),
    path("inventory/requisitions/", views.RequisitionsView.as_view(), name="requisitions"),
]
