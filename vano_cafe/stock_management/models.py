from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import JSONField
from .products_data import PRODUCTS

#Adding a custom field 'role' to the default User model 
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Administrator'),
        ('barista', 'Barista'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    #Methods to identify user roles
    def is_admin(self):
        return self.role == 'admin'
    def is_barista(self):
        return self.role == 'barista'

class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    unit = models.CharField(max_length=15)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    #Method to check if the product is low on stock
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold
    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('ready', 'Ready'),
        ('cancelled', 'Cancelled'),
    )
    barista =  models.ForeignKey(User, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=255)  
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    products = JSONField() 
    def __str__(self):
        return f"Order #{self.id} - {self.status}"
    #Method to add a product to the order
    def add_product(self, product_name, quantity):
        #Initialize the products list if it is empty
        if self.products is None:
            self.products = []
        
        #Retrieve product details from the PRODUCTS data (file products_data.py)
        product_details = PRODUCTS.get(product_name)
        if not product_details:
            raise ValueError(f"Product {product_name} not found in the menu.")
        
        ingredients = product_details["ingredients"]
        price = product_details["price"]
        #Check if sufficient stock exists for each ingredient
        for ingredient, required_qty in ingredients.items():
            try:
                ingredient_obj = Product.objects.get(name=ingredient)
            except Product.DoesNotExist:
                raise ValueError(f"Ingredient {ingredient} not found.")
            
            if ingredient_obj.stock < required_qty * quantity:
                raise ValueError(f"Not enough {ingredient} in stock for {quantity} {product_name}(s).")
        #Deduct the required quantity from stock for each ingredient
        for ingredient, required_qty in ingredients.items():
            ingredient_obj = Product.objects.get(name=ingredient)
            ingredient_obj.stock -= required_qty * quantity
            ingredient_obj.save()
        #Add the product to the order's product list
        self.products.append({
            "name": product_name,
            "quantity": quantity,
            "price": price,
            "ingredients": ingredients,
        })
        #Update the total price of the order and save the order
        self.total_price += price * quantity
        self.save()