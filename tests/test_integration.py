from unittest.mock import patch


def _order_id_from_redirect(response):
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


# ---------- Produits ----------

def test_liste_produits(client):
    r = client.get("/api/products")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["products"]) == 3


# ---------- POST /order ----------

def test_creation_commande_multi_produits(client):
    r = client.post("/order", json={
        "products": [{"id": 1, "quantity": 2}, {"id": 2, "quantity": 1}]
    })
    assert r.status_code == 302

    r = client.get(r.headers["Location"])
    assert r.status_code == 200
    order = r.get_json()["order"]
    assert len(order["products"]) == 2
    assert order["total_price"] == 250  # 100*2 + 50*1
    # 400*2 + 100*1 = 900g → tarif 10
    assert order["shipping_price"] == 10


def test_creation_commande_retro_compat_single_product(client):
    r = client.post("/order", json={"product": {"id": 1, "quantity": 1}})
    assert r.status_code == 302
    r = client.get(r.headers["Location"])
    order = r.get_json()["order"]
    assert len(order["products"]) == 1
    assert order["products"][0] == {"id": 1, "quantity": 1}


def test_creation_sans_produit(client):
    r = client.post("/order", json={})
    assert r.status_code == 422
    assert "product" in r.get_json()["errors"]


def test_creation_produit_hors_stock(client):
    r = client.post("/order", json={"products": [{"id": 3, "quantity": 1}]})
    assert r.status_code == 422
    assert r.get_json()["errors"]["product"]["code"] == "out-of-inventory"


def test_creation_quantite_invalide(client):
    r = client.post("/order", json={"products": [{"id": 1, "quantity": 0}]})
    assert r.status_code == 422


# ---------- GET /order ----------

def test_get_commande_introuvable(client):
    r = client.get("/order/9999")
    assert r.status_code == 404


# ---------- PUT /order (livraison) ----------

def test_update_shipping_info(client, shipping_info):
    r = client.post("/order", json={"products": [{"id": 1, "quantity": 1}]})
    order_id = _order_id_from_redirect(r)

    r = client.put(f"/order/{order_id}", json={
        "order": {"email": "jgnault@uqac.ca", "shipping_information": shipping_info}
    })
    assert r.status_code == 200
    order = r.get_json()["order"]
    assert order["email"] == "jgnault@uqac.ca"
    assert order["shipping_information"]["province"] == "QC"


def test_update_shipping_champs_manquants(client):
    r = client.post("/order", json={"products": [{"id": 1, "quantity": 1}]})
    order_id = _order_id_from_redirect(r)
    r = client.put(f"/order/{order_id}", json={
        "order": {"email": "a@b.c", "shipping_information": {"country": "Canada"}}
    })
    assert r.status_code == 422


# ---------- PUT /order (paiement) ----------

def test_paiement_sans_shipping_info(client, credit_card):
    r = client.post("/order", json={"products": [{"id": 1, "quantity": 1}]})
    order_id = _order_id_from_redirect(r)
    r = client.put(f"/order/{order_id}", json={"credit_card": credit_card})
    assert r.status_code == 422


def test_paiement_async_retourne_202(client, order_ready_to_pay,
                                      credit_card, fake_queue):
    r = client.put(f"/order/{order_ready_to_pay}",
                   json={"credit_card": credit_card})
    assert r.status_code == 202
    assert r.data == b""
    assert len(fake_queue.jobs) == 1


def test_get_pendant_paiement_retourne_202(client, order_ready_to_pay,
                                            credit_card):
    client.put(f"/order/{order_ready_to_pay}",
               json={"credit_card": credit_card})
    r = client.get(f"/order/{order_ready_to_pay}")
    assert r.status_code == 202
    assert r.data == b""


def test_put_pendant_paiement_retourne_409(client, order_ready_to_pay,
                                            credit_card):
    client.put(f"/order/{order_ready_to_pay}",
               json={"credit_card": credit_card})
    r = client.put(f"/order/{order_ready_to_pay}",
                   json={"credit_card": credit_card})
    assert r.status_code == 409


# ---------- Worker + cache ----------

def test_paiement_reussi_met_en_cache(client, order_ready_to_pay,
                                       credit_card, fake_queue, fake_redis,
                                       payment_success_response):
    client.put(f"/order/{order_ready_to_pay}",
               json={"credit_card": credit_card})
    job = fake_queue.jobs[-1]

    with patch("api8inf349.services.call_payment_service",
               return_value=(payment_success_response, 200)):
        job.perform()

    # GET retourne 200 avec paid=true
    r = client.get(f"/order/{order_ready_to_pay}")
    assert r.status_code == 200
    order = r.get_json()["order"]
    assert order["paid"] is True

    # Le cache Redis contient la commande
    cached_key = f"order:{order_ready_to_pay}"
    assert cached_key in fake_redis.store


def test_paiement_reussi_normalise_transaction_success(client,
                                                        order_ready_to_pay,
                                                        credit_card,
                                                        fake_queue,
                                                        payment_success_response):
    client.put(f"/order/{order_ready_to_pay}",
               json={"credit_card": credit_card})
    job = fake_queue.jobs[-1]
    payment_response = {
        **payment_success_response,
        "transaction": {
            **payment_success_response["transaction"],
            "success": "true",
        },
    }

    with patch("api8inf349.services.call_payment_service",
               return_value=(payment_response, 200)):
        job.perform()

    r = client.get(f"/order/{order_ready_to_pay}")
    order = r.get_json()["order"]
    assert order["transaction"]["success"] is True


def test_paiement_reussi_normalise_credit_card_digits(client,
                                                       order_ready_to_pay,
                                                       credit_card,
                                                       fake_queue,
                                                       payment_success_response):
    client.put(f"/order/{order_ready_to_pay}",
               json={"credit_card": credit_card})
    job = fake_queue.jobs[-1]
    payment_response = {
        **payment_success_response,
        "credit_card": {
            **payment_success_response["credit_card"],
            "first_digits": 4242,
            "last_digits": 4242,
        },
    }

    with patch("api8inf349.services.call_payment_service",
               return_value=(payment_response, 200)):
        job.perform()

    r = client.get(f"/order/{order_ready_to_pay}")
    order = r.get_json()["order"]
    assert order["credit_card"]["first_digits"] == "4242"
    assert order["credit_card"]["last_digits"] == "4242"


def test_paiement_echoue_persiste_erreur(client, order_ready_to_pay,
                                          credit_card, fake_queue,
                                          payment_declined_response):
    client.put(f"/order/{order_ready_to_pay}",
               json={"credit_card": credit_card})
    job = fake_queue.jobs[-1]

    with patch("api8inf349.services.call_payment_service",
               return_value=(payment_declined_response, 422)):
        job.perform()

    # GET retourne 200 avec l'erreur dans transaction
    r = client.get(f"/order/{order_ready_to_pay}")
    assert r.status_code == 200
    order = r.get_json()["order"]
    assert order["paid"] is False
    assert order["transaction"]["success"] is False
    assert order["transaction"]["error"]["code"] == "card-declined"


def test_get_utilise_cache_redis(client, order_ready_to_pay, credit_card,
                                  fake_queue, payment_success_response):
    """Après paiement, le GET doit lire depuis Redis (même si la DB change)."""
    client.put(f"/order/{order_ready_to_pay}",
               json={"credit_card": credit_card})
    job = fake_queue.jobs[-1]
    with patch("api8inf349.services.call_payment_service",
               return_value=(payment_success_response, 200)):
        job.perform()

    # Premier GET pour remplir/utiliser le cache
    r1 = client.get(f"/order/{order_ready_to_pay}")
    # On modifie la DB "sous le capot" : le cache doit prévaloir
    from api8inf349.models import Order
    Order.update(total_price=99999).where(Order.id == order_ready_to_pay).execute()

    r2 = client.get(f"/order/{order_ready_to_pay}")
    # Le cache garde l'ancien total_price (pas 99999)
    assert r2.get_json()["order"]["total_price"] != 99999
