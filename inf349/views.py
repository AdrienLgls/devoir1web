from flask import Blueprint, jsonify, request, redirect

from inf349.services import ProductService, OrderService

bp = Blueprint("api", __name__)


@bp.route("/", methods=["GET"])
def get_products():
    products = ProductService.get_all()
    return jsonify({"products": products})


@bp.route("/order", methods=["POST"])
def create_order():
    data = request.get_json(force=True, silent=True)
    order, error = OrderService.create_order(data)

    if error:
        return jsonify(error), 422

    return redirect(f"/order/{order.id}", code=302)


@bp.route("/order/<int:order_id>", methods=["GET"])
def get_order(order_id):
    order = OrderService.get_order(order_id)
    if order is None:
        return "", 404

    return jsonify(order.to_dict())


@bp.route("/order/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    order = OrderService.get_order(order_id)
    if order is None:
        return "", 404

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({
            "errors": {
                "order": {
                    "code": "missing-fields",
                    "name": "Il manque un ou plusieurs champs qui sont obligatoires",
                }
            }
        }), 422

    has_credit_card = "credit_card" in data
    has_order_info = "order" in data

    if has_credit_card and has_order_info:
        return jsonify({
            "errors": {
                "order": {
                    "code": "missing-fields",
                    "name": "Il manque un ou plusieurs champs qui sont obligatoires",
                }
            }
        }), 422

    if has_order_info:
        result, error = OrderService.update_shipping_info(order, data["order"])
        if error:
            return jsonify(error), 422
        return jsonify(result.to_dict())

    if has_credit_card:
        result, error = OrderService.process_payment(order, data["credit_card"])
        if error:
            return jsonify(error), 422
        return jsonify(result.to_dict())

    return jsonify({
        "errors": {
            "order": {
                "code": "missing-fields",
                "name": "Il manque un ou plusieurs champs qui sont obligatoires",
            }
        }
    }), 422
