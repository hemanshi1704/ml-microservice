from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import Portfolio, Transaction


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = ["id", "name", "owner_email", "created_at"]
        read_only_fields = ["id", "created_at"]


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "portfolio", "ticker", "transaction_type",
                  "quantity", "price_per_unit", "executed_at"]
        read_only_fields = ["id"]

    def validate_ticker(self, value):
        return value.strip().upper()

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate_price_per_unit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate(self, attrs):
        # On creation, do not allow selling more than is currently held.
        if self.instance is None and attrs.get("transaction_type") == Transaction.SELL:
            qs = Transaction.objects.filter(portfolio=attrs["portfolio"], ticker=attrs["ticker"])
            bought = qs.filter(transaction_type=Transaction.BUY).aggregate(s=Sum("quantity"))["s"] or Decimal("0")
            sold = qs.filter(transaction_type=Transaction.SELL).aggregate(s=Sum("quantity"))["s"] or Decimal("0")
            if attrs["quantity"] > bought - sold:
                raise serializers.ValidationError("Cannot sell more than the quantity currently held.")
        return attrs
