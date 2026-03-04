import json
from unittest.mock import patch


class TestGetProducts:
    def test_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_returns_products_list(self, client):
        response = client.get("/")
        data = response.get_json()
        assert "products" in data
        assert len(data["products"]) >= 2

    def test_product_has_required_fields(self, client):
        response = client.get("/")
        data = response.get_json()
        product = data["products"][0]
        for field in ["id", "name", "description", "price", "in_stock", "weight", "image"]:
            assert field in product


class TestCreateOrder:
    def test_returns_302_with_location(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": 2}})
        assert response.status_code == 302
        assert "/order/" in response.headers["Location"]

    def test_missing_product_returns_422(self, client):
        response = client.post("/order", json={})
        assert response.status_code == 422
        data = response.get_json()
        assert data["errors"]["product"]["code"] == "missing-fields"

    def test_missing_id_returns_422(self, client):
        response = client.post("/order", json={"product": {"quantity": 1}})
        assert response.status_code == 422

    def test_missing_quantity_returns_422(self, client):
        response = client.post("/order", json={"product": {"id": 1}})
        assert response.status_code == 422

    def test_quantity_zero_returns_422(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": 0}})
        assert response.status_code == 422

    def test_negative_quantity_returns_422(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": -1}})
        assert response.status_code == 422

    def test_nonexistent_product_returns_422(self, client):
        response = client.post("/order", json={"product": {"id": 9999, "quantity": 1}})
        assert response.status_code == 422

    def test_out_of_stock_returns_422(self, client):
        response = client.post("/order", json={"product": {"id": 3, "quantity": 1}})
        assert response.status_code == 422
        data = response.get_json()
        assert data["errors"]["product"]["code"] == "out-of-inventory"


class TestGetOrder:
    def test_returns_order(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": 1}})
        location = response.headers["Location"]

        response = client.get(location)
        assert response.status_code == 200
        data = response.get_json()
        assert data["order"]["product"]["id"] == 1
        assert data["order"]["paid"] is False
        assert data["order"]["credit_card"] == {}
        assert data["order"]["shipping_information"] == {}
        assert data["order"]["transaction"] == {}

    def test_not_found_returns_404(self, client):
        response = client.get("/order/99999")
        assert response.status_code == 404

    def test_shipping_price_calculated(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": 1}})
        location = response.headers["Location"]
        response = client.get(location)
        data = response.get_json()
        assert data["order"]["shipping_price"] == 500


class TestUpdateShippingInfo:
    def _create_order(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": 1}})
        return response.headers["Location"]

    def _valid_shipping_data(self):
        return {
            "order": {
                "email": "test@uqac.ca",
                "shipping_information": {
                    "country": "Canada",
                    "address": "201, rue Pr\u00e9sident-Kennedy",
                    "postal_code": "G7X 3Y7",
                    "city": "Chicoutimi",
                    "province": "QC",
                },
            }
        }

    def test_update_shipping_returns_200(self, client):
        location = self._create_order(client)
        response = client.put(location, json=self._valid_shipping_data())
        assert response.status_code == 200

    def test_email_saved(self, client):
        location = self._create_order(client)
        client.put(location, json=self._valid_shipping_data())
        response = client.get(location)
        data = response.get_json()
        assert data["order"]["email"] == "test@uqac.ca"

    def test_tax_calculated_qc(self, client):
        location = self._create_order(client)
        client.put(location, json=self._valid_shipping_data())
        response = client.get(location)
        data = response.get_json()
        assert data["order"]["total_price_tax"] > data["order"]["total_price"]

    def test_missing_email_returns_422(self, client):
        location = self._create_order(client)
        data = self._valid_shipping_data()
        del data["order"]["email"]
        response = client.put(location, json=data)
        assert response.status_code == 422

    def test_missing_shipping_field_returns_422(self, client):
        location = self._create_order(client)
        data = self._valid_shipping_data()
        del data["order"]["shipping_information"]["city"]
        response = client.put(location, json=data)
        assert response.status_code == 422

    def test_nonexistent_order_returns_404(self, client):
        response = client.put("/order/99999", json=self._valid_shipping_data())
        assert response.status_code == 404


class TestPayment:
    def _setup_order_for_payment(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": 1}})
        location = response.headers["Location"]
        client.put(location, json={
            "order": {
                "email": "test@uqac.ca",
                "shipping_information": {
                    "country": "Canada",
                    "address": "201, rue Pr\u00e9sident-Kennedy",
                    "postal_code": "G7X 3Y7",
                    "city": "Chicoutimi",
                    "province": "QC",
                },
            }
        })
        return location

    def _valid_credit_card(self):
        return {
            "credit_card": {
                "name": "John Doe",
                "number": "4242 4242 4242 4242",
                "expiration_year": 2030,
                "cvv": "123",
                "expiration_month": 9,
            }
        }

    @patch("inf349.services.call_payment_service")
    def test_successful_payment(self, mock_pay, client):
        mock_pay.return_value = (
            {
                "credit_card": {
                    "name": "John Doe",
                    "first_digits": "4242",
                    "last_digits": "4242",
                    "expiration_year": 2030,
                    "expiration_month": 9,
                },
                "transaction": {
                    "id": "abc123",
                    "success": True,
                    "amount_charged": 528,
                },
            },
            200,
        )
        location = self._setup_order_for_payment(client)
        response = client.put(location, json=self._valid_credit_card())
        assert response.status_code == 200
        data = response.get_json()
        assert data["order"]["paid"] is True
        assert data["order"]["transaction"]["success"] is True
        assert data["order"]["credit_card"]["first_digits"] == "4242"
        assert data["order"]["credit_card"]["last_digits"] == "4242"

    @patch("inf349.services.call_payment_service")
    def test_declined_card(self, mock_pay, client):
        mock_pay.return_value = (
            {
                "errors": {
                    "credit_card": {
                        "code": "card-declined",
                        "name": "La carte de cr\u00e9dit a \u00e9t\u00e9 d\u00e9clin\u00e9e.",
                    }
                }
            },
            422,
        )
        location = self._setup_order_for_payment(client)
        card = self._valid_credit_card()
        card["credit_card"]["number"] = "4000 0000 0000 0002"
        response = client.put(location, json=card)
        assert response.status_code == 422
        data = response.get_json()
        assert data["errors"]["credit_card"]["code"] == "card-declined"

    @patch("inf349.services.call_payment_service")
    def test_already_paid_returns_422(self, mock_pay, client):
        mock_pay.return_value = (
            {
                "credit_card": {
                    "name": "John Doe",
                    "first_digits": "4242",
                    "last_digits": "4242",
                    "expiration_year": 2030,
                    "expiration_month": 9,
                },
                "transaction": {
                    "id": "abc123",
                    "success": True,
                    "amount_charged": 528,
                },
            },
            200,
        )
        location = self._setup_order_for_payment(client)
        client.put(location, json=self._valid_credit_card())

        response = client.put(location, json=self._valid_credit_card())
        assert response.status_code == 422
        data = response.get_json()
        assert data["errors"]["order"]["code"] == "already-paid"

    def test_payment_without_shipping_returns_422(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": 1}})
        location = response.headers["Location"]

        response = client.put(location, json=self._valid_credit_card())
        assert response.status_code == 422

    def test_credit_card_and_order_together_returns_422(self, client):
        response = client.post("/order", json={"product": {"id": 1, "quantity": 1}})
        location = response.headers["Location"]

        response = client.put(location, json={
            "credit_card": {"name": "John Doe", "number": "4242 4242 4242 4242"},
            "order": {"email": "test@uqac.ca"},
        })
        assert response.status_code == 422

    @patch("inf349.services.call_payment_service")
    def test_full_flow(self, mock_pay, client):
        mock_pay.return_value = (
            {
                "credit_card": {
                    "name": "John Doe",
                    "first_digits": "4242",
                    "last_digits": "4242",
                    "expiration_year": 2030,
                    "expiration_month": 9,
                },
                "transaction": {
                    "id": "xyz789",
                    "success": True,
                    "amount_charged": 528,
                },
            },
            200,
        )

        response = client.post("/order", json={"product": {"id": 1, "quantity": 1}})
        assert response.status_code == 302
        location = response.headers["Location"]

        response = client.get(location)
        assert response.status_code == 200
        data = response.get_json()
        assert data["order"]["paid"] is False

        response = client.put(location, json={
            "order": {
                "email": "test@uqac.ca",
                "shipping_information": {
                    "country": "Canada",
                    "address": "201, rue Pr\u00e9sident-Kennedy",
                    "postal_code": "G7X 3Y7",
                    "city": "Chicoutimi",
                    "province": "QC",
                },
            }
        })
        assert response.status_code == 200

        response = client.put(location, json={
            "credit_card": {
                "name": "John Doe",
                "number": "4242 4242 4242 4242",
                "expiration_year": 2030,
                "cvv": "123",
                "expiration_month": 9,
            }
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["order"]["paid"] is True
        assert data["order"]["email"] == "test@uqac.ca"
        assert data["order"]["transaction"]["id"] == "xyz789"
