from django.contrib import messages
from django.shortcuts import render
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from .models import Product, Order, User
from django.views.decorators.csrf import csrf_exempt
from django.db.models import F
from .products_data import PRODUCTS
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from stock_management.forms import ProductForm, CustomUserEditForm
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

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


@csrf_exempt
def order_creation(request):
    if request.method == "POST":
        # Retrieve form data
        selected_products = request.POST.getlist("products[]")
        products_to_add = {}

        # Parse and validate product quantities
        for item in selected_products:
            product_name, quantity = item.split(":")
            quantity = int(quantity)
            if quantity < 1:
                messages.error(request, f"Invalid quantity for {product_name}")
                return redirect("create_order")

            # Check if the product exists in PRODUCTS and calculate stock impact
            for category, product_data in PRODUCTS.items():
                if product_name in product_data:
                    ingredients = product_data[product_name]["ingredients"]
                    for ingredient, required_amount in ingredients.items():
                        product = Product.objects.get(name=ingredient)
                        if product.stock < required_amount * quantity:
                            messages.error(request, f"Not enough stock for {ingredient}")
                            return redirect("create_order")
                    # Add to order if stock is sufficient
                    products_to_add[product_name] = quantity
                    break

        # Deduct stock from ingredients
        for product_name, quantity in products_to_add.items():
            for category, product_data in PRODUCTS.items():
                if product_name in product_data:
                    ingredients = product_data[product_name]["ingredients"]
                    for ingredient, required_amount in ingredients.items():
                        product = Product.objects.get(name=ingredient)
                        product.stock -= required_amount * quantity
                        product.save()

        # Create the order
        order = Order.objects.create(
            barista=request.user,
            status="paid",
            total_price=sum(
                PRODUCTS[cat][name]["price"] * qty
                for cat, prod in PRODUCTS.items()
                for name, details in prod.items()
                for name, qty in products_to_add.items()
            ),
            products=products_to_add,  # JSON data with products and quantities
        )

        messages.success(request, "Order successfully created!")
        return redirect("order_queue")

    # Render the product selection form
    context = {"PRODUCTS": PRODUCTS}
    return render(request, "order_creation.html", context)

def order_queue(request):
    if not request.user.is_barista():
        return redirect('login')  # Redirect non-barista users
    active_orders = Order.objects.filter(status='paid', barista=request.user)
    return render(request, 'order_queue.html', {'active_orders': active_orders})

def mark_ready(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = 'ready'
    order.save()
    return redirect('order_queue')

def order_history(request):
    if not request.user.is_barista():
        return redirect('login')  # Redirect non-barista users
    orders = Order.objects.filter(barista=request.user, created_at__gte=request.user.last_login)
    return render(request, 'order_history.html', {'orders': orders})

def admin_dashboard(request):
    if not request.user.is_admin():
        return redirect('login')  # Redirect non-admin users
    low_stock_products = Product.objects.filter(stock__lte=F('low_stock_threshold'))
    return render(request, 'admin_dashboard.html', {'low_stock_products': low_stock_products})

def stock_management(request):
    if not request.user.is_admin():
        return redirect('login')  # Redirect non-admin users
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

# Update an existing product (Update)
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

# Delete a product (Delete)
def stock_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        return redirect('stock_management')
    return render(request, 'stock_confirm_delete.html', {'product': product})

def user_management(request):
    if not request.user.is_admin():
        return redirect('login')  # Redirect non-admin users
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
                return redirect('user_management')  # Redirect to the user management page after update
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
        # Display products in the specified category
        products = PRODUCTS.get(category, {})
        if not products:
            # Handle case where category doesn't exist
            return render(request, "error.html", {"message": "Category not found."})
        context = {"category": category, "products": products}
    else:
        # Show all categories
        context = {"categories": PRODUCTS.keys()}
    
    return render(request, "order_creation.html", context)