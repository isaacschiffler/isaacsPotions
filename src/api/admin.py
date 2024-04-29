from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """
    with db.engine.begin() as connection:
                # reset global_inventory
                result = connection.execute(sqlalchemy.text("SELECT * FROM globe;")) # for debugging
                globe = result.fetchone()
                print("Current database status before reset: " + str(globe[0]) + " " + str(globe[1]) + " " + str(globe[2]) + " " + str(globe[3]) + " " + str(globe[4])) # for debugging

                
                # reset/clear cart stuff and ledgers
                connection.execute(sqlalchemy.text("DELETE FROM cart_items"))
                connection.execute(sqlalchemy.text("DELETE FROM carts"))
                connection.execute(sqlalchemy.text("DELETE FROM barrel_ledger"))
                connection.execute(sqlalchemy.text("DELETE FROM potion_ledger"))
                connection.execute(sqlalchemy.text("DELETE FROM gold_ledger"))
                connection.execute(sqlalchemy.text("DELETE FROM capacity_ledger"))
                connection.execute(sqlalchemy.text("DELETE FROM processed"))

                # set starting values
                connection.execute(sqlalchemy.text("INSERT INTO gold_ledger (gold) VALUES (100)"))
                connection.execute(sqlalchemy.text("INSERT INTO capacity_ledger (ml_capacity, potion_capacity) VALUES (10000, 50)"))

                 
    return "OK"

