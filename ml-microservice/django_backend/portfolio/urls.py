from rest_framework.routers import DefaultRouter

from .views import PortfolioViewSet, TransactionViewSet

router = DefaultRouter()
router.register("portfolios", PortfolioViewSet, basename="portfolio")
router.register("transactions", TransactionViewSet, basename="transaction")

urlpatterns = router.urls
