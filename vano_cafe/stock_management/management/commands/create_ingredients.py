from django.core.management.base import BaseCommand
from stock_management.models import Product
from stock_management.products_data import PRODUCTS

class Command(BaseCommand):
    help = 'Create missing products for ingredients if not already present in the database.'

    def handle(self, *args, **kwargs):
        for category, products in PRODUCTS.items():
            for product_name, details in products.items():
                ingredients = details["ingredients"]
                for ingredient, qty in ingredients.items():
                    if not Product.objects.filter(name=ingredient).exists():
                        Product.objects.create(name=ingredient, category="ingredient", unit="pc", price=0.01, stock=1000, low_stock_threshold=100)  # Default stock
                        self.stdout.write(self.style.SUCCESS(f'Created product for ingredient: {ingredient}'))

        self.stdout.write(self.style.SUCCESS('Finished creating missing products for ingredients.'))