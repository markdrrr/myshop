from django.contrib.auth import authenticate, login
from django.shortcuts import render, get_object_or_404
from django.views.generic import DetailView, View
from .forms import *
from .mixins import *
from .models import *
from django.db import models, transaction
from django.http import HttpResponseRedirect
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from .utils import recalc_cart


class BaseView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        products = Product.objects.all()
        ct_models = ContentType.objects.filter(model__in=('notebook', 'smartphone'))
        for ct_model in ct_models:
            model_products = ct_model.model_class()._base_manager.all().order_by('-id')[:5]
            products.extend(model_products)
        context = {
            'categories': self.categories,
            'products': products,
            'cart': self.cart
        }
        return render(request, 'base.html', context)


class ProductDetailView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        product = Product.objects.get(slug=kwargs['slug'])
        context = {
            'categories': self.categories,
            'product': product,
            'cart': self.cart
        }
        return render(request, 'product_detail.html', context)
# def product_detail_view(request, slug):
#     products = Product.objects.get(slug=slug)
#     categories = Category.objects.all()
#     context = {'product': products, 'categories': categories}
#     # достаем карзину
#     if request.user.is_authenticated:
#         customer = Customer.objects.filter(user=request.user).first()
#         if not customer:
#             customer = Customer.objects.create(
#                 user=request.user
#             )
#         cart = Cart.objects.filter(owner=customer, in_order=False).first()
#         if not cart:
#             cart = Cart.objects.create(owner=customer)
#     else:
#         cart = Cart.objects.filter(for_anonymous_user=True).first()
#         if not cart:
#             cart = Cart.objects.create(for_anonymous_user=True)
#     context["cart"] = cart
#     return render(request, 'product_detail.html', context)


class CategoryDetailView(CartMixin, DetailView):

    def get(self, request, *args, **kwargs):
        category = Category.objects.get(slug=kwargs['slug'])
        products = Product.objects.filter(category=category)
        context = {
            'cart': self.cart,
            'categories': self.categories,
            'products': products,
            'category': category
        }
        return render(request, 'category_detail.html', context)


class AddToCartView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect('/login/')
        product_slug = kwargs.get('slug')
        product = Product.objects.get(slug=product_slug)
        cart_product, created = CartProduct.objects.get_or_create(
            user=self.cart.owner, cart=self.cart, product=product
        )
        self.cart.products.add(cart_product)
        recalc_cart(self.cart)
        messages.add_message(request, messages.INFO, "Товар успешно добавлен")
        return HttpResponseRedirect('/cart/')


class DeleteFromCartView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        product_slug = kwargs.get('slug')
        product = Product.objects.get(slug=product_slug)
        cart_product = CartProduct.objects.get(
            user=self.cart.owner, cart=self.cart, product=product
        )
        self.cart.products.remove(cart_product)
        cart_product.delete()
        recalc_cart(self.cart)
        messages.add_message(request, messages.INFO, "Товар успешно удален")
        return HttpResponseRedirect('/cart/')


class ChangeCountView(CartMixin, View):

    def post(self, request, *args, **kwargs):
        product_slug = kwargs.get('slug')
        product = Product.objects.get(slug=product_slug)
        cart_product = CartProduct.objects.get(
            user=self.cart.owner, cart=self.cart, product=product
        )
        count = int(request.POST.get('count'))
        cart_product.count = count
        cart_product.save()
        recalc_cart(self.cart)
        messages.add_message(request, messages.INFO, "Кол-во успешно изменено")
        return HttpResponseRedirect('/cart/')


class CartView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect('/login/')
        context = {
            'cart': self.cart,
            'categories': self.categories
        }
        return render(request, 'cart.html', context)


class CheckoutView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        form = OrderForm(request.POST or None)
        context = {
            'cart': self.cart,
            'categories': self.categories,
            'form': form
        }
        return render(request, 'checkout.html', context)


class MakeOrderView(CartMixin, View):

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = OrderForm(request.POST or None)
        if request.user.is_authenticated:
            customer = Customer.objects.get(user=request.user)
        if form.is_valid():
            new_order = form.save(commit=False)
            new_order.customer = customer
            # print([f.name for f in new_order._meta.get_fields()])
            # print(new_order._meta.get_field('first_name'))
            for el in ['first_name', 'last_name', 'phone', 'address', 'buying_type', 'order_date', 'comment']:
                value = new_order._meta.get_field(el)
                value.field = form.cleaned_data[el]
            new_order.save()
            self.cart.in_order = True
            recalc_cart(self.cart)
            new_order.cart = self.cart
            new_order.save()
            if new_order.customer:
                customer.orders.add(new_order)
            messages.add_message(request, messages.INFO, 'Спасибо за заказ! Менеджер с Вами свяжется')
            return HttpResponseRedirect('/')
        return HttpResponseRedirect('/checkout/')


class LoginView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        form = LoginForm(request.POST or None)
        context = {
            'cart': self.cart,
            'categories': self.categories,
            'form': form
        }
        return render(request, 'login.html', context)

    def post(self, request, *args, **kwargs):
        form = LoginForm(request.POST or None)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                return HttpResponseRedirect('/')
        context = {
            'cart': self.cart,
            'categories': self.categories,
            'form': form
        }
        return render(request, 'login.html', context)


class RegistrationView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        form = RegistrationForm(request.POST or None)
        context = {
            'cart': self.cart,
            'categories': self.categories,
            'form': form
        }
        return render(request, 'registration.html', context)

    def post(self, request, *args, **kwargs):
        form = RegistrationForm(request.POST or None)
        if form.is_valid():
            new_user = form.save(commit=False)
            for el in ['username', 'email', 'first_name', 'last_name']:
                value = new_user._meta.get_field(el)
                value.field = form.cleaned_data[el]
            new_user.set_password(form.cleaned_data['password'])
            new_user.save()
            Customer.objects.create(user=new_user, phone=form.cleaned_data['phone'],
                                    address=form.cleaned_data['address'])
            user = authenticate(username=form.cleaned_data['username'], password=form.cleaned_data['password'])
            login(request, user)
            return HttpResponseRedirect('/')
        context = {
            'cart': self.cart,
            'categories': self.categories,
            'form': form
        }
        return render(request, 'registration.html', context)


class ProfileView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        customer = Customer.objects.get(user=request.user)
        orders = Order.objects.filter(customer=customer).order_by('-created_at')
        context = {
            'cart': self.cart,
            'categories': self.categories,
            'orders': orders
        }
        return render(request, 'profile.html', context)
