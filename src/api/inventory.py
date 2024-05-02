from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
import sqlalchemy
from src import database as db


router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """ """
    with db.engine.begin() as connection:
        globe = connection.execute(sqlalchemy.text("SELECT * FROM globe")).fetchone()
        gold = globe.gold
        ml = globe.red_ml + globe.blue_ml + globe.green_ml + globe.dark_ml

        num_potions = connection.execute(sqlalchemy.text("SELECT SUM(quantity) FROM potions")).fetchone()[0]
    
    return {"number_of_potions": num_potions, "ml_in_barrels": ml, "gold": gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    add_p_cap = 0
    add_ml_cap = 0

    with db.engine.begin() as connection:
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM globe")).fetchone()[0]
        potion_count = connection.execute(sqlalchemy.text("SELECT SUM(quantity) FROM potions")).fetchone()[0]
        mls = connection.execute(sqlalchemy.text("SELECT red_ml, green_ml, blue_ml, dark_ml, ml_capacity, potion_capacity from globe")).fetchone()
        ml_count = mls.red_ml + mls.green_ml + mls.blue_ml + mls.dark_ml
        ml_cap = mls.ml_capacity
        potion_cap = mls.potion_capacity
    
    if ml_count > (.75 * ml_cap) and gold > 1000:
        gold -= 1000
        add_ml_cap = 1
    
    if potion_count > (.75 * potion_cap) and gold > 1000:
        gold -= 1000
        add_p_cap = 1

    return {
        "potion_capacity": add_p_cap,
        "ml_capacity": add_ml_cap
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    mls = capacity_purchase.ml_capacity * 10000
    potions = capacity_purchase.potion_capacity * 50
    gold = capacity_purchase.ml_capacity + capacity_purchase.potion_capacity
    with db.engine.begin() as connection:
        # add to processed
        trans_id = connection.execute(sqlalchemy.text("""INSERT INTO processed
                                           (job_id, type) VALUES
                                           (:job_id, 'capacity') returning id"""),
                                           [{
                                               'job_id': order_id
                                           }]).fetchone()[0]

        # add to capacity ledger
        connection.execute(sqlalchemy.text("""INSERT INTO capacity_ledger 
                                           (trans_id, ml_capacity, potion_capacity) VALUES
                                           (:trans_id, :mls, :potions)"""),
                                           [{
                                               'trans_id': trans_id,
                                               'mls': mls,
                                               'potions': potions
                                           }])
        
        # add order to gold_ledger
        connection.execute(sqlalchemy.text("""INSERT INTO gold_ledger
                                           (trans_id, gold) VALUES
                                           (:trans_id, :cost);
                                           """), 
                                           [{
                                               'trans_id': trans_id,
                                               'cost': -gold
                                           }])

    return "OK"
