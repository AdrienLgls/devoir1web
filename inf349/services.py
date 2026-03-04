import json
import urllib.request

from inf349.models import Product, Order

PRODUCTS_URL = "http://dimensweb.uqac.ca/~jgnault/shops/products/"
PAYMENT_URL = "http://dimensweb.uqac.ca/~jgnault/shops/pay/"

TAX_RATES = {
    "QC": 0.15,
    "ON": 0.13,
    "AB": 0.05,
    "BC": 0.12,
    "NS": 0.14,
}


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
        return json.loads(e.read().decode()), e.code


def calculate_shipping_price(weight):
    if weight <= 500:
        return 500
    elif weight <= 2000:
        return 1000
    else:
        return 2500


class ProductService:
    @classmethod
    def get_all(cls):
        return [p.to_dict() for p in Product.select()]


class OrderService:
    @classmethod
    def create_order(cls, data):
        if not data or "product" not in data:
            return None, {
                "errors": {
                    "product": {
                        "code": "missing-fields",
                        "name": "La cr\u00e9ation d'une commande n\u00e9cessite un produit",
                    }
                }
            }

        product_data = data["product"]

        if "id" not in product_data or "quantity" not in product_data:
            return None, {
                "errors": {
                    "product": {
                        "code": "missing-fields",
                        "name": "La cr\u00e9ation d'une commande n\u00e9cessite un produit",
                    }
                }
            }

        quantity = product_data["quantity"]
        if not isinstance(quantity, int) or quantity < 1:
            return None, {
                "errors": {
                    "product": {
                        "code": "missing-fields",
                        "name": "La cr\u00e9ation d'une commande n\u00e9cessite un produit",
                    }
                }
            }

        product = Product.get_or_none(Product.id == product_data["id"])
        if product is None:
            return None, {
                "errors": {
                    "product": {
                        "code": "missing-fields",
                        "name": "La cr\u00e9ation d'une commande n\u00e9cessite un produit",
                    }
                }
            }

        if not product.in_stock:
            return None, {
                "errors": {
                    "product": {
                        "code": "out-of-inventory",
                        "name": "Le produit demand\u00e9 n'est pas en inventaire",
                    }
                }
            }

        total_weight = product.weight * quantity
        shipping_price = calculate_shipping_price(total_weight)
        total_price = round(product.price * quantity)

        order = Order.create(
            product_id=product.id,
            quantity=quantity,
            total_price=total_price,
            shipping_price=shipping_price,
        )

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

        province = shipping_info.get("province", "")
        tax_rate = TAX_RATES.get(province, 0)
        total_price_tax = round(order.total_price * (1 + tax_rate), 2)

        order.email = email
        order.shipping_information = json.dumps(shipping_info)
        order.total_price_tax = total_price_tax
        order.save()

        return order, None

    @classmethod
    def process_payment(cls, order, credit_card_data):
        if order.paid:
            return None, {
                "errors": {
                    "order": {
                        "code": "already-paid",
                        "name": "La commande a d\u00e9j\u00e0 \u00e9t\u00e9 pay\u00e9e.",
                    }
                }
            }

        shipping_info = order.shipping_information
        if isinstance(shipping_info, str):
            shipping_info = json.loads(shipping_info)

        if not order.email or not shipping_info:
            return None, {
                "errors": {
                    "order": {
                        "code": "missing-fields",
                        "name": "Les informations du client sont n\u00e9cessaire avant d'appliquer une carte de cr\u00e9dit",
                    }
                }
            }

        amount_charged = order.total_price + order.shipping_price
        response_data, status_code = call_payment_service(credit_card_data, amount_charged)

        if status_code != 200:
            if "errors" in response_data:
                return None, {"errors": response_data["errors"]}
            if "credit_card" in response_data:
                return None, {"errors": {"credit_card": response_data["credit_card"]}}
            return None, response_data

        order.credit_card = json.dumps({
            "name": credit_card_data.get("name", ""),
            "first_digits": credit_card_data.get("number", "")[:4],
            "last_digits": credit_card_data.get("number", "")[-4:],
            "expiration_year": credit_card_data.get("expiration_year"),
            "expiration_month": credit_card_data.get("expiration_month"),
        })
        order.transaction = json.dumps(response_data.get("transaction", {}))
        order.paid = True
        order.save()

        return order, None
