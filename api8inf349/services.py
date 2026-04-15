import json
import urllib.request
import urllib.error

from api8inf349.models import Product, Order, OrderProduct, order_to_dict, db
from api8inf349.cache import cache_order

PRODUCTS_URL = "https://dimensweb.uqac.ca/~jgnault/shops/products/"
PAYMENT_URL = "https://dimensweb.uqac.ca/~jgnault/shops/pay/"


def fetch_products():
    req = urllib.request.Request(PRODUCTS_URL)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
    return data.get("products", [])


def call_payment_service(credit_card, amount_charged):
    payload = json.dumps({
        "credit_card": credit_card,
        "amount_charged": amount_charged,
    }).encode()

    req = urllib.request.Request(
        PAYMENT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()), response.status
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return (json.loads(body) if body else {}), e.code


def calculate_shipping_price(weight):
    if weight <= 500:
        return 5
    elif weight <= 2000:
        return 10
    else:
        return 25


def _missing_product_error():
    return {
        "errors": {
            "product": {
                "code": "missing-fields",
                "name": "La création d'une commande nécessite un produit",
            }
        }
    }


class ProductService:
    @classmethod
    def get_all(cls):
        return [p.to_dict() for p in Product.select()]


class OrderService:
    @classmethod
    def create_order(cls, data):
        if not data:
            return None, _missing_product_error()

        # Supporter les deux formats: "product" (single) et "products" (multi)
        items = []
        if "products" in data and isinstance(data["products"], list):
            items = data["products"]
        elif "product" in data:
            items = [data["product"]]
        else:
            return None, _missing_product_error()

        if not items:
            return None, _missing_product_error()

        validated = []
        total_weight = 0
        total_price = 0

        for item in items:
            if not isinstance(item, dict):
                return None, _missing_product_error()
            if "id" not in item or "quantity" not in item:
                return None, _missing_product_error()
            quantity = item["quantity"]
            if not isinstance(quantity, int) or quantity < 1:
                return None, _missing_product_error()
            product = Product.get_or_none(Product.id == item["id"])
            if product is None:
                return None, _missing_product_error()
            if not product.in_stock:
                return None, {
                    "errors": {
                        "product": {
                            "code": "out-of-inventory",
                            "name": "Le produit demandé n'est pas en inventaire",
                        }
                    }
                }
            validated.append((product, quantity))
            total_weight += product.weight * quantity
            total_price += product.price * quantity

        shipping_price = calculate_shipping_price(total_weight)

        with db.atomic():
            order = Order.create(
                total_price=round(total_price),
                shipping_price=shipping_price,
            )
            for product, quantity in validated:
                OrderProduct.create(order=order, product=product, quantity=quantity)

        return order, None

    @classmethod
    def get_order(cls, order_id):
        return Order.get_or_none(Order.id == order_id)

    @classmethod
    def update_shipping_info(cls, order, order_data):
        email = order_data.get("email")
        shipping_info = order_data.get("shipping_information")

        if not email or not shipping_info:
            return None, {
                "errors": {
                    "order": {
                        "code": "missing-fields",
                        "name": "Il manque un ou plusieurs champs qui sont obligatoires",
                    }
                }
            }

        for field in ["country", "address", "postal_code", "city", "province"]:
            if field not in shipping_info or not shipping_info[field]:
                return None, {
                    "errors": {
                        "order": {
                            "code": "missing-fields",
                            "name": "Il manque un ou plusieurs champs qui sont obligatoires",
                        }
                    }
                }

        order.email = email
        order.shipping_information = json.dumps(shipping_info)
        order.save()

        return order, None

    @classmethod
    def validate_payment_request(cls, order, credit_card_data):
        """Valide les prérequis avant de lancer le paiement en arrière-plan."""
        if order.paid:
            return {
                "errors": {
                    "order": {
                        "code": "already-paid",
                        "name": "La commande a déjà été payée.",
                    }
                }
            }

        shipping_info = order.shipping_information
        if isinstance(shipping_info, str):
            shipping_info = json.loads(shipping_info) if shipping_info else {}

        if not order.email or not shipping_info:
            return {
                "errors": {
                    "order": {
                        "code": "missing-fields",
                        "name": "Les informations du client sont nécessaire avant d'appliquer une carte de crédit",
                    }
                }
            }

        if not credit_card_data:
            return {
                "errors": {
                    "order": {
                        "code": "missing-fields",
                        "name": "Il manque un ou plusieurs champs qui sont obligatoires",
                    }
                }
            }

        return None


def process_payment_task(order_id, credit_card):
    """Tâche RQ : exécute le paiement en arrière-plan."""
    if db.is_closed():
        db.connect()

    try:
        order = Order.get_by_id(order_id)
        amount_charged = order.total_price + order.shipping_price
        response_data, status_code = call_payment_service(credit_card, amount_charged)

        if status_code == 200:
            order.credit_card = json.dumps(response_data.get("credit_card", {}))
            order.transaction = json.dumps(response_data.get("transaction", {}))
            order.paid = True
            order.processing = False
            order.save()
            cache_order(order_to_dict(order))
        else:
            errors = response_data.get("errors", {}) if isinstance(response_data, dict) else {}
            error_obj = errors.get("credit_card") or next(iter(errors.values()), {})
            transaction = {
                "success": False,
                "error": error_obj,
                "amount_charged": amount_charged,
            }
            order.transaction = json.dumps(transaction)
            order.processing = False
            order.save()
    finally:
        if not db.is_closed():
            db.close()
