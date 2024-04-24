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

# this functions updates quant of potions we have in inventory when deliveries occur
def update_potions(type, quantity, connection):
    tuple_type = tuple(type)
    name = potion_names[tuple_type]
    sku = name.upper()
    sku = sku.replace(' ', '_')
    sku += "_0"
    result = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory WHERE sku = :sku LIMIT 1;"), 
                                {'sku': sku})
    row = result.fetchone()
    # check for existence in case we are making a new potion recipe we haven't before and its not in the database
    if not row:
        # insert
        price = type[0] * .5 + type[1] * .5 + type[2] * .6 + type[3] * .7 # basic price assignment just based on quantity of each potion color included...
        connection.execute(sqlalchemy.text("INSERT INTO potion_inventory (sku, r, g, b, d, quantity, name, price) VALUES (:sku, :r, :g, :b, :d, :quant, :name, :price);"), 
                           {'sku': sku,
                            'r': type[0],
                            'g': type[1],
                            'b': type[2],
                            'd': type[3],
                            'quant': quantity,
                            'name': name,
                            'price': price
                            })
        print("inserting potion type: " + str(type))
    else:
        # update
        print("Current potion updating: " + str(row))
        current_quant = row.quantity
        connection.execute(sqlalchemy.text("""
                                    UPDATE potion_inventory
                                    SET quantity = :quant
                                    WHERE sku = :sku;
                                    """),
                                    {'quant': quantity + current_quant, 
                                     'name': name,
                                     'sku': sku})
    

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
        # for i in potions_delivered:
        #     update_potions(i.potion_type, i.quantity, connection)

        # g_inventory = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        # globe = g_inventory.fetchone()
        # red_ml = globe.num_red_ml
        # green_ml = globe.num_green_ml
        # blue_ml = globe.num_blue_ml
        # dark_ml = globe.num_dark_ml

        # # subtract potion mats used
        # green_ml -= green_quant
        # red_ml -= red_quant
        # blue_ml -= blue_quant
        # dark_ml -= dark_quant

        # update ml in database
        # connection.execute(sqlalchemy.text("""
        #                             UPDATE global_inventory
        #                             SET num_green_ml = :green, num_red_ml = :red, num_blue_ml = :blue, num_dark_ml = :dark
        #                             WHERE id = 1;
        #                             """),
        #                             {'green': green_ml, 'red': red_ml, 'blue': blue_ml, 'dark': dark_ml})
        
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

    Basic logic for now: Make as many solid color potions as possible
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    with db.engine.begin() as connection:
        globe = connection.execute(sqlalchemy.text("SELECT * FROM globe")).fetchone()
        red_ml = globe.red_ml
        green_ml = globe.green_ml
        blue_ml = globe.blue_ml
        dark_ml = globe.dark_ml

        potion_inventory = connection.execute(sqlalchemy.text("SELECT * FROM potions ORDER BY quantity ASC;")).fetchall()

        # # create a potion_order
        # id = connection.execute(sqlalchemy.text("""INSERT INTO potion_orders returning id;""")).fetchone().id

        # potion_ids = []
        # current logic is to just make solid color potions
        bottle_plan = make_bottles(red_ml, green_ml, blue_ml, dark_ml, potion_inventory)
        
        # # finish this!!!!!!
        # connection.execute(sqlalchemy.text("""INSERT INTO potion_order_items
        #                                    (potion_id, order_id, quantity) VALUES
        #                                    (:potion_id, :order_id, :quantity)"""),
        #                                    potion_ids)



    print(bottle_plan) # for debugging
        
    return bottle_plan



"""Initial thoughts: We should probably try to have a large array of potions
available, and have a decent stock of basic pure potions, also a decent stock 
of high profit yielding potions and high purchase potions..."""
# potion_stock is a sql query result that returns all potions sorted by least quantity in stock
# red, green, blue, dark is the ml quantities we have in our global inventory for each respective color
def make_bottles(red, green, blue, dark, potion_stock):
    # to start lets just make a potion with proportions based on what we have lowest stock of and can make given ml stock
    bottle_plan = []
    total_ml = red + green + blue + dark
    for row in potion_stock:
        if total_ml < 100:
            # get out if we don't even have 100 ml of potion
            break
        # try to make the current potion
        potion_type = row.type
        quant_wanted = 0
        # make up to 3 potions as possible
        while red >= potion_type[0] and green >= potion_type[1] and blue >= potion_type[2] and dark >= potion_type[3] and quant_wanted < 3:
            quant_wanted += 1
            red -= potion_type[0]
            green -= potion_type[1]
            blue -= potion_type[2]
            dark -= potion_type[3]
        if quant_wanted > 0:
            bottle_plan.append({
                "potion_type": potion_type,
                "quantity": quant_wanted
            })

    return bottle_plan


if __name__ == "__main__":
    print(get_bottle_plan())