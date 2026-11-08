from django.urls import path
from apps.finance import operations
from apps.finance import views as FinanceViews

app_name = "finance"

urlpatterns = [
    path("accounting/cashier/", FinanceViews.CashierView.as_view(), name="finance-cashier"),
    path("accounting/invoices/", FinanceViews.InvoicesView.as_view(), name="finance-invoices"),
    path("accounting/invoices/<int:pk>/", FinanceViews.InvoiceDetailView.as_view(), name="finance-invoice"),
    path("accounting/ledger/", FinanceViews.FinancesView.as_view(), name="finance-finances"),
    path("accounting/insurance/", FinanceViews.InsuranceView.as_view(), name="finance-insurance"),
    path("accounting/insurance/<str:kind>/<int:pk>/", FinanceViews.CompanyDetailView.as_view(), name="finance-company"),
    path("accounting/price-lists/", FinanceViews.PricingView.as_view(), name="finance-pricing"),
    path("accounting/mpesa/", operations.MpesaView.as_view(), name="mpesa"),
    path("accounting/shifts/", operations.ShiftsView.as_view(), name="shifts"),
    path("accounting/claims/", operations.ClaimsView.as_view(), name="claims"),
    path("accounting/claims/<int:pk>/", operations.ClaimDetailView.as_view(), name="claim"),
    path("accounting/etims/", operations.EtimsView.as_view(), name="etims"),
    path("accounting/chart-of-accounts/", operations.ChartOfAccountsView.as_view(), name="chart-of-accounts"),
    path("accounting/chart-of-accounts/<int:pk>/", operations.LedgerAccountDetailView.as_view(), name="ledger-account"),
    path("accounting/banks/", operations.BanksView.as_view(), name="banks"),
    path("accounting/banks/<int:pk>/", operations.BankDetailView.as_view(), name="bank"),
]
