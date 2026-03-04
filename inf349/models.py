import json

from peewee import (
    SqliteDatabase,
    Model,
    AutoField,
    IntegerField,
    CharField,
    BooleanField,
    FloatField,
    TextField,
)

db = SqliteDatabase("inf349.db")


class BaseModel(Model):
    class Meta:
        database = db


class Product(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField()
    description = CharField(default="")
    price = FloatField()
    in_stock = BooleanField()
    weight = IntegerField()
    image = CharField(default="")

    def to_dict(self):
        return {
            "name": self.name,
            "id": self.id,
            "in_stock": self.in_stock,
            "description": self.description,
            "price": self.price,
            "weight": self.weight,
            "image": self.image,
        }


class Order(BaseModel):
    id = AutoField()
    product_id = IntegerField()
    quantity = IntegerField()
    total_price = IntegerField(default=0)
    total_price_tax = FloatField(default=0)
    email = CharField(null=True)
    paid = BooleanField(default=False)
    shipping_price = IntegerField(default=0)

    shipping_information = TextField(default="{}")
    credit_card = TextField(default="{}")
    transaction = TextField(default="{}")

    def _parse_json(self, field_value):
        if isinstance(field_value, str):
            return json.loads(field_value) if field_value else {}
        return field_value

    def to_dict(self):
        return {
            "order": {
                "id": self.id,
                "total_price": self.total_price,
                "total_price_tax": self.total_price_tax,
                "email": self.email,
                "credit_card": self._parse_json(self.credit_card),
                "shipping_information": self._parse_json(self.shipping_information),
                "paid": self.paid,
                "transaction": self._parse_json(self.transaction),
                "product": {
                    "id": self.product_id,
                    "quantity": self.quantity,
                },
                "shipping_price": self.shipping_price,
            }
        }
