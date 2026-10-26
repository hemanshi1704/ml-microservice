from django.db import models
from django.utils import timezone


class Portfolio(models.Model):
    name = models.CharField(max_length=100)
    owner_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    BUY = "BUY"
    SELL = "SELL"
    TYPE_CHOICES = [(BUY, "Buy"), (SELL, "Sell")]

    portfolio = models.ForeignKey(Portfolio, related_name="transactions", on_delete=models.CASCADE)
    ticker = models.CharField(max_length=15)
    transaction_type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    price_per_unit = models.DecimalField(max_digits=14, decimal_places=4)
    executed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["executed_at", "id"]

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} {self.ticker}"


class PriceCache(models.Model):
    """Daily closing prices pulled from Yahoo Finance."""
    ticker = models.CharField(max_length=15, db_index=True)
    date = models.DateField()
    close = models.DecimalField(max_digits=14, decimal_places=4)

    class Meta:
        unique_together = ("ticker", "date")
        ordering = ["ticker", "date"]

    def __str__(self):
        return f"{self.ticker} {self.date} {self.close}"
