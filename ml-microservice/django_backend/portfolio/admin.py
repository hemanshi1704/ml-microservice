from django.contrib import admin

from .models import Portfolio, PriceCache, Transaction

admin.site.register(Portfolio)
admin.site.register(Transaction)
admin.site.register(PriceCache)
