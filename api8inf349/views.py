from flask import jsonify, request, redirect, render_template

from api8inf349.services import ProductService, OrderService, process_payment_task
from api8inf349.models import order_to_dict
from api8inf349.cache import get_cached_order
from api8inf349.queue import get_queue


def register_routes(app):

    @app.route("/", methods=["GET"])
    def index():
        if request.accept_mimetypes.best == "application/json" or request.args.get("format") == "json":
            return jsonify({"products": ProductService.get_all()})
        return render_template("index.html", products=ProductService.get_all())

    @app.route("/api/products", methods=["GET"])
    def get_products_json():
        return jsonify({"products": ProductService.get_all()})

    @app.route("/order-lookup", methods=["GET"])
    def order_lookup():
        order_id = request.args.get("order_id")
        if not order_id:
            return redirect("/")
        return redirect(f"/order/{order_id}")

    @app.route("/order", methods=["POST"])
    def create_order():
        if request.is_json:
            data = request.get_json(force=True, silent=True)
        else:
            # Support formulaires HTML
            form_ids = request.form.getlist("product_id")
            form_qty = request.form.getlist("quantity")
            products = []
            for pid, q in zip(form_ids, form_qty):
                try:
                    if int(q) > 0:
                        products.append({"id": int(pid), "quantity": int(q)})
                except (TypeError, ValueError):
                    pass
            data = {"products": products} if products else None

        order, error = OrderService.create_order(data)

        if error:
            if request.is_json:
                return jsonify(error), 422
            return render_template("error.html", error=error), 422

        return redirect(f"/order/{order.id}", code=302)

    @app.route("/order/<int:order_id>", methods=["GET"])
    def get_order(order_id):
        cached = get_cached_order(order_id)
        if cached is not None:
            if _wants_html():
                return render_template("order.html", order=cached["order"])
            return jsonify(cached)

        order = OrderService.get_order(order_id)
        if order is None:
            return "", 404

        if order.processing:
            return "", 202

        payload = order_to_dict(order)
        if _wants_html():
            return render_template("order.html", order=payload["order"])
        return jsonify(payload)

    @app.route("/order/<int:order_id>", methods=["PUT"])
    def update_order(order_id):
        order = OrderService.get_order(order_id)
        if order is None:
            return "", 404

        if order.processing:
            return "", 409

        data = request.get_json(force=True, silent=True)
        if not data:
            return _missing_fields_error()

        has_credit_card = "credit_card" in data
        has_order_info = "order" in data

        if has_credit_card and has_order_info:
            return _missing_fields_error()

        if has_order_info:
            result, error = OrderService.update_shipping_info(order, data["order"])
            if error is not None:
                return jsonify(error), 422
            return jsonify(order_to_dict(result))

        if has_credit_card:
            error = OrderService.validate_payment_request(order, data["credit_card"])
            if error is not None:
                return jsonify(error), 422
            order.processing = True
            order.save()
            get_queue().enqueue(process_payment_task, order.id, data["credit_card"])
            return "", 202

        return _missing_fields_error()

    # Routes HTML supplémentaires (formulaires HTML ne supportent que GET/POST)
    @app.route("/order/<int:order_id>/shipping", methods=["POST"])
    def submit_shipping(order_id):
        order = OrderService.get_order(order_id)
        if order is None:
            return "", 404
        payload = {
            "order": {
                "email": request.form.get("email"),
                "shipping_information": {
                    "country": request.form.get("country"),
                    "address": request.form.get("address"),
                    "postal_code": request.form.get("postal_code"),
                    "city": request.form.get("city"),
                    "province": request.form.get("province"),
                },
            }
        }
        result, error = OrderService.update_shipping_info(order, payload["order"])
        if error:
            return render_template("error.html", error=error), 422
        return redirect(f"/order/{order_id}", code=302)

    @app.route("/order/<int:order_id>/pay", methods=["POST"])
    def submit_payment(order_id):
        order = OrderService.get_order(order_id)
        if order is None:
            return "", 404
        if order.processing:
            return render_template("error.html", error={
                "errors": {"order": {"code": "processing", "name": "Paiement en cours"}}
            }), 409
        credit_card = {
            "name": request.form.get("name"),
            "number": request.form.get("number"),
            "expiration_year": _safe_int(request.form.get("expiration_year")),
            "expiration_month": _safe_int(request.form.get("expiration_month")),
            "cvv": request.form.get("cvv"),
        }
        error = OrderService.validate_payment_request(order, credit_card)
        if error:
            return render_template("error.html", error=error), 422
        order.processing = True
        order.save()
        get_queue().enqueue(process_payment_task, order.id, credit_card)
        return redirect(f"/order/{order_id}", code=302)


def _wants_html():
    fmt = request.args.get("format")
    if fmt == "json":
        return False
    if fmt == "html":
        return True
    accept = request.accept_mimetypes
    return accept.best_match(["application/json", "text/html"]) == "text/html"


def _missing_fields_error():
    return jsonify({
        "errors": {
            "order": {
                "code": "missing-fields",
                "name": "Il manque un ou plusieurs champs qui sont obligatoires",
            }
        }
    }), 422


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
