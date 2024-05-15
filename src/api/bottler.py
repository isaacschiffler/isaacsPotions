from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db


router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int


# naming conventions for potion recipes that we utilize
potion_names = {
    (100, 0, 0, 0): "red potion",
    (0, 100, 0, 0): "green potion",
    (0, 0, 100, 0): "blue potion",
    (0, 0, 0, 100): "dark potion",
    (33, 34, 33, 0): "white potion",
    (50, 0, 50, 0): "purple potion",
    (50, 50, 0, 0): "yellow potion",
    (0, 50, 50, 0): "teal potion",
    (0, 0, 0, 100): "dark potion"
}
    

@router.post("/newRecipe")
def add_new_recipe(type: list[int], name: str):
    """ add a new potion recipe to potion_types, don't insert a potion_type that already exists pls... """
    sku = name.upper()
    sku = sku.replace(' ', '_')
    sku += "_0"
    price = type[0] * .5 + type[1] * .5 + type[2] * .6 + type[3] * .7 # basic price assignment just based on quantity of each potion color included...

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("""INSERT INTO potion_types
                                           (sku, name, price, type) VALUES
                                           (:sku, :name, :price, :type)"""),
                                           [{
                                               'sku': sku,
                                               'name': name,
                                               'price': price,
                                               'type': type
                                           }])


    return "New potion created; sku: " + sku


@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    #subtract ml and add potions
    """ """
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    green_quant = 0
    red_quant = 0
    blue_quant = 0
    dark_quant = 0
    for i in potions_delivered:
        red_quant += i.potion_type[0] * i.quantity
        green_quant += i.potion_type[1] * i.quantity
        blue_quant += i.potion_type[2] * i.quantity
        dark_quant += i.potion_type[3] * i.quantity

    with db.engine.begin() as connection:        
        # insert into processed table
        trans_id = connection.execute(sqlalchemy.text("""INSERT INTO processed
                                                (job_id, type) VALUES
                                                (:job_id, 'potion_brew') returning id;"""),
                                                [{
                                                    'job_id': order_id
                                                }]).fetchone()[0]
        
        # insert into barrel_ledger
        connection.execute(sqlalchemy.text("""INSERT INTO barrel_ledger
                                           (red_ml, green_ml, blue_ml, dark_ml, trans_id) VALUES
                                           (:red_ml, :green_ml, :blue_ml, :dark_ml, :trans_id)"""),
                                           [{
                                               'red_ml': -red_quant,
                                               'green_ml': -green_quant,
                                               'blue_ml': -blue_quant,
                                               'dark_ml': -dark_quant,
                                               'trans_id': trans_id
                                           }])
        
        for i in potions_delivered:
            # insert each potion brewed into potion_ledger
            connection.execute(sqlalchemy.text("""INSERT INTO potion_ledger
                                               (potion_id, trans_id, quantity) 
                                               SELECT id, :trans_id, :quantity
                                               FROM potion_types
                                               WHERE type = :type;"""),
                                               [{
                                                   'trans_id': trans_id,
                                                   'quantity': i.quantity,
                                                   'type': i.potion_type
                                               }])


    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.

    Basic logic for now: Make up to 3 additional potions starting from least stocked
    """
    with db.engine.begin() as connection:
        globe = connection.execute(sqlalchemy.text("SELECT red_ml, green_ml, blue_ml, dark_ml, potion_capacity, ml_capacity FROM globe")).fetchone()
        red_ml = globe.red_ml
        green_ml = globe.green_ml
        blue_ml = globe.blue_ml
        dark_ml = globe.dark_ml
        ml_count = red_ml + green_ml + blue_ml + dark_ml
        capacity = globe.potion_capacity
        ml_cap = globe.ml_capacity

        # pick out what portion of capacity we want to make for each potion (terrible description...)
        if ml_count < (ml_cap / 3):
            potion_portionator = 12
        elif ml_count < (ml_cap / 2):
            potion_portionator = 8
        else:
            potion_portionator = 5

        potion_inventory = connection.execute(sqlalchemy.text("SELECT type, quantity FROM potions ORDER BY quantity ASC;")).fetchall()
        potion_count = connection.execute(sqlalchemy.text("SELECT SUM(quantity) FROM potions")).fetchone()[0]

        bottle_plan = make_bottles(red_ml, green_ml, blue_ml, dark_ml, potion_inventory, capacity, potion_count, potion_portionator)

    print(bottle_plan) # for debugging
        
    return bottle_plan



"""Initial thoughts: We should probably try to have a large array of potions
available, and have a decent stock of basic pure potions, also a decent stock 
of high profit yielding potions and high purchase potions..."""
# potion_stock is a sql query result that returns all potions sorted by least quantity in stock
# red, green, blue, dark is the ml quantities we have in our global inventory for each respective color
def make_bottles(red, green, blue, dark, potion_stock, capacity, potion_count, portioner):
    # to start lets just make a potion with proportions based on what we have lowest stock of and can make given ml stock
    bottle_plan = []

    for row in potion_stock:
        # don't make any more lime potions... sad flop... also don't make whites anymore i think
        if row.type == [30, 70, 0, 0] or row.type == [34, 33, 33, 0]:
            continue
        # try to make the current potion
        potion_type = row.type
        if row.quantity >= (capacity / 9):
            # don't make any more if we already have a decent amount, make others
            continue
        quant_wanted = 0
        # make up to 3 potions as possible
        while red >= potion_type[0] and green >= potion_type[1] and blue >= potion_type[2] and dark >= potion_type[3] and quant_wanted < (capacity // 10):
            if (row.quantity + quant_wanted) > (capacity / 9):
                continue
            quant_wanted += 1
            red -= potion_type[0]
            green -= potion_type[1]
            blue -= potion_type[2]
            dark -= potion_type[3]
        if quant_wanted > 0 and potion_count + quant_wanted <= capacity:
            bottle_plan.append({
                "potion_type": potion_type,
                "quantity": quant_wanted
            })
            potion_count += quant_wanted

    return bottle_plan


if __name__ == "__main__":
    print(get_bottle_plan())