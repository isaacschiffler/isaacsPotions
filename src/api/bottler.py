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

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    #subtract ml and add potions
    """ """
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    order_quantity = 0
    for i in potions_delivered:
        if i.potion_type == [0, 100, 0, 0]:
            order_quantity += i.quantity

    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        green = result.fetchone()
        num_potions = green[2]
        num_green_ml = green[3]
        id = 1 # hard coded because right now we only have one row... change when more complex
        ml = order_quantity * 100
        connection.execute(sqlalchemy.text("""
                                    UPDATE global_inventory
                                    SET num_green_ml = :ml, num_green_potions = :potions
                                    WHERE id = :id;
                                    """),
                                    {'ml': num_green_ml - ml, 'potions': num_potions + order_quantity, 'id': id})


    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into green potions.

    bottle_plan = []

    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        green = result.fetchone()
        ml = green[3]
        quantity = ml // 100 #calculate how many potions of 100 ml of green we can make (floor function)

    if quantity > 0:
        bottle_plan.append({
                "potion_type": [0, 100, 0, 0], #hard coded to create just green potions for now...
                "quantity": quantity,
        })
    print(bottle_plan) # for debugging
        

    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())