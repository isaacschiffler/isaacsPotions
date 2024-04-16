from fastapi import APIRouter
import sqlalchemy
from src import database as db
import random

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """
    my_catalog = []

    with db.engine.begin() as connection:
        # get all potions we have in stock
        result = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory WHERE quantity > 0;"))
        for row in result:
            print("Adding to catalog: " + str(row))
            sku = row[0]
            type = [row[1], row[2], row[3], row[4]]
            quantity = row[5]
            name = row[6]
            price = row[7]
            print("Number of " + str(type) + " potions offered: " + str(quantity))
            if quantity > 0: # should be unecessary because of our query params but fail-safe
                my_catalog.append({
                    "sku": sku,
                    "name": name,
                    "quantity": quantity,
                    "price": price,
                    "potion_type": type,
                })

    print(my_catalog) # for debugging

    return my_catalog