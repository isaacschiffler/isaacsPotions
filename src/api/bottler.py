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


def update_potions(type, quantity, connection):
    result = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory WHERE r = :r AND g = :g AND b = :b AND d = :d LIMIT 1"), 
                                {'r': type[0],
                                 'g': type[1],
                                 'b': type[2],
                                 'd': type[3]})
    row = result.fetchone()
    # check for existence!
    if not row:
        # insert
        connection.execute(sqlalchemy.text("INSERT INTO potion_inventory (r, g, b, d, quantity) VALUES (:r, :g, :b, :d, :quant)"), 
                           {'r': type[0],
                            'g': type[1],
                            'b': type[2],
                            'd': type[3],
                            'quant': quantity})
        print("inserting potion type: " + str(type))
    else:
        # update
        print("Current potion updating: " + str(row))
        current_quant = row[5]
        connection.execute(sqlalchemy.text("""
                                    UPDATE potion_inventory
                                    SET quantity = :quant
                                    WHERE r = :r AND g = :g AND b = :b AND d = :d;
                                    """),
                                    {'quant': quantity + current_quant, 
                                     'r': type[0],
                                     'g': type[1],
                                     'b': type[2],
                                     'd': type[3]})
    

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    #subtract ml and add potions
    """ """
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    green_quant = 0
    red_quant = 0
    blue_quant = 0
    dark_quant = 0
    # for i in potions_delivered:
    #     # check what type of potion and store the quantity we get
    #     if i.potion_type == [0, 100, 0, 0]:
    #         green_quant += i.quantity
    #     elif i.potion_type == [100, 0, 0, 0]:
    #         red_quant += i.quantity
    #     elif i.potion_type == [0, 0, 100, 0]:
    #         blue_quant += i.quantity
    #     else:
    #         print("somehow got delivered a non-solid color potion...") # version 2 debug impl
    for i in potions_delivered:
        red_quant += i.potion_type[0] * i.quantity
        green_quant += i.potion_type[1] * i.quantity
        blue_quant += i.potion_type[2] * i.quantity
        dark_quant += i.potion_type[3] * i.quantity

    with db.engine.begin() as connection:
        g_inventory = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        # p_inventory = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory"))
        for i in potions_delivered:
            update_potions(i.potion_type, i.quantity, connection)
        # for row in p_inventory:
        #     #row[1] = potion type, row[2] = quantity
        #     if row[1] == [100, 0, 0, 0]: # solid red potion count
        #         num_red_potions = row[2]
        #         if red_quant > 0:
        #             update_potions(row[1], num_red_potions + red_quant, connection)
        #     elif row[1] == [0, 100, 0, 0]: # solid green
        #         num_green_potions = row[2]
        #         if green_quant > 0:
        #             update_potions(row[1], num_green_potions + green_quant, connection)
        #     elif row[1] == [0, 0, 100, 0]: # solid blue
        #         num_blue_potions = row[2]
        #         if blue_quant > 0:
        #             update_potions(row[1], num_blue_potions + blue_quant, connection)
        globe = g_inventory.fetchone()
        red_ml = globe[2]
        green_ml = globe[3]
        blue_ml = globe[4]
        # subtract potion mats used
        green_ml -= green_quant
        red_ml -= red_quant
        blue_ml -= blue_quant
        # update ml in database
        connection.execute(sqlalchemy.text("""
                                    UPDATE global_inventory
                                    SET num_green_ml = :green, num_red_ml = :red, num_blue_ml = :blue
                                    WHERE id = 1;
                                    """),
                                    {'green': green_ml, 'red': red_ml, 'blue': blue_ml})
        # DOUBLE CHECK AND TEST EVERYTHING ---------------------------------------------------------------------------------------------------------


    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.

    Basic logic for now: Make as many solid color potions as possible
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into green potions.

    bottle_plan = []

    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        globe = result.fetchone()
        red_ml = globe[2]
        green_ml = globe[3]
        blue_ml = globe[4]
        green_quant = green_ml // 100 #calculate how many potions of 100 ml of green we can make (floor function)
        red_quant = red_ml // 100
        blue_quant = blue_ml // 100

    # current logic is to just make solid color potions
    if green_quant > 0:
        bottle_plan.append({
                "potion_type": [0, 100, 0, 0],
                "quantity": green_quant,
        })
    if red_quant > 0:
        bottle_plan.append({
                "potion_type": [100, 0, 0, 0],
                "quantity": red_quant,
        })
    if blue_quant > 0:
        bottle_plan.append({
                "potion_type": [0, 0, 100, 0],
                "quantity": blue_quant,
        })

    print(bottle_plan) # for debugging
        

    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())