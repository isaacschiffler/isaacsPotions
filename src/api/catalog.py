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
        result = connection.execute(sqlalchemy.text("""SELECT potion_types.sku, potions.quantity, potion_types.name, potion_types.type, potion_types.price
                                                    FROM potion_types 
                                                    JOIN potions ON potion_types.type = potions.type
                                                    WHERE potions.quantity > 0 
                                                    ORDER BY potions.quantity ASC
                                                    LIMIT 10;""")).fetchall()
        
        for row in result:
            if row.type == [50, 0, 50, 0]:
                # no ____ today!
                continue
            print("Adding to catalog: " + str(row))
            sku = row.sku
            type = row.type
            quantity = row.quantity
            name = row.name
            price = row.price
            print("Number of " + str(type) + " potions offered: " + str(quantity))
            if quantity > 0: # should be unecessary because of our query params but fail-safe
                my_catalog.append({
                    "sku": sku,
                    "name": name,
                    "quantity": quantity,
                    "price": price,
                    "potion_type": type,
                })
            if len(my_catalog) >= 6:
                break

    print(my_catalog) # for debugging

    return my_catalog