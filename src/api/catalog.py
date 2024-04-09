from fastapi import APIRouter
import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """
    my_catalog = []

    '''use start database connection green_potion_inventory = get current inventory of green potions'''
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        row = result.fetchone()
        num_green_potions = row[2]
        print("Number of green potions offered: " + str(num_green_potions))
        if num_green_potions > 0:
            num_green_potions = 1 #only offering 1 potion for now...
            my_catalog.append({
                "sku": "GREEN_POTION_0",
                "name": "green potion",
                "quantity": num_green_potions,
                "price": 50,
                "potion_type": [0, 100, 0, 0],
            })


    return my_catalog
