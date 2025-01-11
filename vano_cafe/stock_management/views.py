from django.contrib import messages
from django.shortcuts import render
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from .models import Product, Order, User
from django.db import transaction
from django.db.models import F
from .products_data import PRODUCTS
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from stock_management.forms import ProductForm, CustomUserEditForm
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render
from django.db.models import Sum, Count
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from collections import Counter

def custom_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_admin():
                return redirect('admin_dashboard')
            else:
                return redirect('order_creation')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def order_creation(request):
    filtered_products = {}
    products_max_quantity = {}

    for category, products in PRODUCTS.items():
        filtered_products[category] = {}
        for product_name, details in products.items():
            ingredients = details["ingredients"]
            try:
                max_quantity = min(
                    Product.objects.get(name=ingredient).stock // required_amount
                    for ingredient, required_amount in ingredients.items()
                )
                if max_quantity > 0:
                    filtered_products[category][product_name] = details
                    products_max_quantity[product_name] = max_quantity
            except Product.DoesNotExist as e:
                print(f"Ingredient not found: {e}")
                continue

    if request.method == "POST":
        products_to_add = []
        
        for key, value in request.POST.items():
            if key.startswith("products-quantity-"):
                product_name_key = key.replace("products-quantity-", "products-name-")
                quantity = int(value)
                product_name = request.POST.get(product_name_key)

                if quantity > 0:

                    for category, product_data in PRODUCTS.items():
                        if product_name in product_data:
                            ingredients = product_data[product_name]["ingredients"]
                            price = product_data[product_name]["price"]

                            for ingredient, required_amount in ingredients.items():
                                product = Product.objects.get(name=ingredient)
                                if product.stock < required_amount * quantity:
                                    messages.error(request, f"Not enough stock for {ingredient}")
                                    return redirect("create_order")
                            
                            products_to_add.append({
                                "name": product_name,
                                "quantity": quantity,
                                "price": price,
                            })
                            break

        total_price = sum(product["price"] * product["quantity"] for product in products_to_add)

        for product in products_to_add:
            product_name = product["name"]
            quantity = product["quantity"]
            ingredients = next(
                prod[product_name]["ingredients"]
                for cat, prod in PRODUCTS.items()
                if product_name in prod
            )
            for ingredient, required_amount in ingredients.items():
                product_obj = Product.objects.get(name=ingredient)
                product_obj.stock -= required_amount * quantity
                product_obj.save()

        order = Order.objects.create(
            barista=request.user,
            status="paid",
            total_price=total_price,
            products=products_to_add,
        )

        messages.success(request, "Order successfully created!")
        return redirect("order_queue")

    return render(request, "order_creation.html", {
        "PRODUCTS": filtered_products,
        "products_max_quantity": products_max_quantity,
    })

def order_queue(request):
    orders = Order.objects.filter(status="paid")

    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')
        order = Order.objects.get(id=order_id)

        if action == "mark_ready" and order.status != 'ready':
            order.status = 'ready'
            order.save()

        elif action == "cancel_order" and order.status != 'cancelled':

            order.status = 'cancelled'

            try:
                with transaction.atomic():

                    for product in order.products:  
                        print(f"Processing product: {product}") 
                        product_name = product.get('name')
                        quantity = product.get('quantity')

                        if product_name and quantity:
                            try:
                                product_obj = Product.objects.get(name=product_name.strip().lower())
                                print(f"Found product: {product_obj}")
                                product_obj.stock += quantity
                                product_obj.save()
                            except Product.DoesNotExist:
                                print(f"Error: Product {product_name} does not exist in the database.")
                        else:
                            print(f"Invalid product data: {product}")

                    order.save()
                    print(f"Order {order.id} has been cancelled and stock updated.") 
            except Exception as e:
                print(f"Error during order cancellation: {e}")

        return redirect('order_queue') 

    for order in orders:
        order.parsed_products = []
        for product in order.products: 
            product_name = product.get('name')
            quantity = product.get('quantity')
            price = product.get('price')

            order.parsed_products.append({
                "name": product_name,
                "quantity": quantity,
                "price": price,
            })

    return render(request, "order_queue.html", {"orders": orders})

def order_history(request):
    ready_orders = Order.objects.filter(status='ready')
    cancelled_orders = Order.objects.filter(status='cancelled')
    
    return render(request, 'order_history.html', {
        'ready_orders': ready_orders,
        'cancelled_orders': cancelled_orders,
    })

def admin_dashboard(request):
    if not request.user.is_admin():
        return redirect('login')
    low_stock_products = Product.objects.filter(stock__lte=F('low_stock_threshold'))
    # 1. Total Sales: Sum of all order total prices (from Order model)
    total_sales = Order.objects.filter(status='paid').aggregate(Sum('total_price'))['total_price__sum'] or 0

    # 2. Most Popular Products: Use the 'products' JSONField to calculate product quantities
    # We'll extract product names from the products field and count occurrences
    orders = Order.objects.filter(status='paid')
    all_products = []

    for order in orders:
        for product in order.products:
            all_products.append(product['name'])

    # Count occurrences of each product name (total quantity sold)
    product_counts = Counter(all_products)
    most_popular_products = product_counts.most_common(5)  # Get the top 5 most popular products

    # 3. Sales of All Products: Calculate total quantity sold for each product
    sales_data = Counter()
    for order in orders:
        for product in order.products:
            sales_data[product['name']] += product['quantity']  # Sum up quantities for each product

    # Create a bar graph for sales per product
    product_names = list(sales_data.keys())
    quantities = list(sales_data.values())

    plt.figure(figsize=(10, 6))
    plt.bar(product_names, quantities, color='skyblue')
    plt.xlabel('Product')
    plt.ylabel('Quantity Sold')
    plt.title('Sales per Product')

    # Save the plot to a BytesIO buffer
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_data = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()

    # 4. Additional statistics (e.g., average order value)
    total_orders = orders.count()
    avg_order_value = total_sales / total_orders if total_orders > 0 else 0

    # Pass data to the template
    context = {
        'total_sales': total_sales,
        'most_popular_products': most_popular_products,
        'sales_chart': image_data,
        'avg_order_value': avg_order_value,
    }
    return render(request, 'admin_dashboard.html', context, {'low_stock_products': low_stock_products})

def stock_management(request):
    if not request.user.is_admin():
        return redirect('login')
    products = Product.objects.all()
    return render(request, 'stock_management.html', {'products': products})

def stock_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('stock_management')
    else:
        form = ProductForm()
    return render(request, 'stock_form.html', {'form': form, 'action': 'Create'})

def stock_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('stock_management')
    else:
        form = ProductForm(instance=product)
    return render(request, 'stock_form.html', {'form': form, 'action': 'Update'})

def stock_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        return redirect('stock_management')
    return render(request, 'stock_confirm_delete.html', {'product': product})

def user_management(request):
    if not request.user.is_admin():
        return redirect('login') 
    users = User.objects.all()
    return render(request, 'user_management.html', {'users': users})

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_admin()

class UserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = User
    template_name = 'user_list.html'
    context_object_name = 'users'

class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = User
    fields = ['username', 'role', 'password']
    template_name = 'user_form.html'
    success_url = reverse_lazy('user_management')

    def form_valid(self, form):
        form.instance.set_password(form.cleaned_data['password'])
        return super().form_valid(form)

class UserUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserEditForm
    template_name = 'user_form.html'
    success_url = reverse_lazy('user_management')

    def edit_user(request, pk):
        user = get_object_or_404(User, pk=pk)
        if request.method == 'POST':
            form = CustomUserEditForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                return redirect('user_management')
        else:
            form = CustomUserEditForm(instance=user)

        return render(request, 'edit_user.html', {'form': form, 'user': user})

class UserDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = User
    template_name = 'user_confirm_delete.html'
    success_url = reverse_lazy('user_management')

def display_products(request, category=None):
    """
    View to display products by category. If no category is specified, show all categories.
    """
    if category:
        products = PRODUCTS.get(category, {})
        if not products:
            return render(request, "error.html", {"message": "Category not found."})
        context = {"category": category, "products": products}
    else:
        context = {"categories": PRODUCTS.keys()}
    
    return render(request, "order_creation.html", context)