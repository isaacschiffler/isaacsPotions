from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

'''
with db.engine.begin() as connection:
    result = connection.execute(sqlalchemy.text(sql_to_execute))
'''

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    #subtract price and add ml
    """ """
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")

    for i in barrels_delivered:
    
        quantity = i.quantity
        ml = i.ml_per_barrel
        price = i.price
        id = 1 # hard coded because we only have one row... change when more complex

        if i.potion_type == [0, 1, 0, 0]:
            with db.engine.begin() as connection:
                result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
                green = result.fetchone()
                print(green)
                num_green_ml = green[3]
                gold = green[4]

                connection.execute(sqlalchemy.text("""
                                                UPDATE global_inventory
                                                SET num_green_ml = :ml, gold = :gold
                                                WHERE id = :id;
                                                """),  
                                                {'ml': (ml * quantity) + num_green_ml, 'gold': gold - (price * quantity), 'id': id})
    
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)

    what_i_want = []

    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        green = result.fetchone()
        print(green)
        num_green_potions = green[2]
        gold = green[4]
        buy_num = 0
        for i in wholesale_catalog:
            available = i.quantity
            if i.potion_type == [0, 1, 0, 0]:
                while gold >= i.price and available > 0:
                    buy_num += 1
                    gold -= i.price
                    available -= 1
            what_i_want.append({
                "sku": i.sku,
                "quantity": buy_num
            })
        if num_green_potions >= 10:
            buy_num = 0
            what_i_want = [{
                "sku": "nothing",
                "quantity": 0
            }]


    return what_i_want

