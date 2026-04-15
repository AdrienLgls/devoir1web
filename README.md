# api8inf349 — Projet de session 8INF349 (Partie 2)

Application Flask de paiement de commandes avec PostgreSQL, Redis et RQ.

## Équipe

Voir `CODES-PERMANENTS`.

## Prérequis

- Python 3.6+
- PostgreSQL 12
- Redis 5
- Docker (optionnel)

## Installation

```bash
pip install -r requirements.txt
```

## Lancer les dépendances avec Docker

```bash
docker-compose up -d
```

Cela démarre PostgreSQL (port 5432) et Redis (port 6379).

## Initialisation de la base de données

```bash
export FLASK_DEBUG=True
export FLASK_APP=api8inf349
export REDIS_URL=redis://localhost
export DB_HOST=localhost
export DB_USER=user
export DB_PASSWORD=pass
export DB_PORT=5432
export DB_NAME=api8inf349

flask init-db
```

## Lancer l'application

```bash
flask run
```

## Lancer le gestionnaire de tâches (worker RQ)

Dans un autre terminal, avec les mêmes variables d'environnement :

```bash
flask worker
```

## Build Docker

```bash
docker build -t api8inf349 .
docker run -e REDIS_URL=redis://host.docker.internal \
           -e DB_HOST=host.docker.internal \
           -e DB_USER=user -e DB_PASSWORD=pass \
           -e DB_PORT=5432 -e DB_NAME=api8inf349 \
           -p 5000:5000 api8inf349
```

## API

- `GET /` — page HTML listant les produits (ou JSON avec `?format=json`)
- `GET /api/products` — JSON des produits
- `POST /order` — crée une commande (1 ou plusieurs produits)
- `GET /order/<id>` — affiche la commande (JSON ou HTML, avec cache Redis)
- `PUT /order/<id>` — met à jour livraison ou déclenche paiement async

## Interface HTML

Les pages accessibles depuis `/` permettent de créer une commande,
entrer l'information de livraison et payer via des formulaires HTML.
