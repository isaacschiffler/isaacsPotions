from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db


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


    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        globe = result.fetchone()
        print("Current database status: " + str(globe[1]) + " " + str(globe[2]) + " " + str(globe[3])) #for debugging
        gold = globe[1]
        num_red_ml = globe[2]
        num_green_ml = globe[3]
        num_blue_ml = globe[4]
        new_green = 0
        new_red = 0
        new_blue = 0
        cost = 0

        for i in barrels_delivered:
            quantity = i.quantity
            ml = i.ml_per_barrel
            type = i.potion_type
            price = i.price
            if type == [0, 1, 0, 0]: # if a green barrel
                new_green += ml * quantity
            elif type == [1, 0, 0, 0]: # if a red barrel
                new_red += ml * quantity
            elif type == [0, 0, 1, 0]: # if a blue barrel
                new_blue += ml * quantity
            else: # not green, red, or blue
                print("potion delivered that is not red, green, or blue.......")
            cost += price * quantity
            

        connection.execute(sqlalchemy.text("""
                                        UPDATE global_inventory
                                        SET num_green_ml = :green, gold = :gold, num_red_ml = :red, num_blue_ml = :blue
                                        WHERE id = 1;
                                        """),  
                                        {'green': new_green + num_green_ml, 'gold': gold - cost, 
                                            'red': new_red + num_red_ml, 'blue': new_blue + num_blue_ml})
    
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """Basic Logic: try to buy a barrel for the color potion mat we have least of. If none are affordable, try to buy a different color.
    Also, buy based on best value after color is selected.
    Turns out this is pretty dumb because bottler is called all the time so we usually have 0 of every barrel... maybe better when we have more gold???"""
    print(wholesale_catalog)

    what_i_want = []

    with db.engine.begin() as connection:
        g_inventory = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        globe = g_inventory.fetchone()
        print("Current database status: " + str(globe[1]) + " " + str(globe[2]) + " " + str(globe[3]) + " " + str(globe[4]) + " " + str(globe[5]))
        gold = globe[1]
        # get current ml inventory
        red_ml = globe[2]
        green_ml = globe[3]
        blue_ml = globe[4]
        # get catalog offerings for each color barrel
        red_offers = [x for x in wholesale_catalog if x.potion_type == [1, 0, 0, 0]]
        green_offers = [x for x in wholesale_catalog if x.potion_type == [0, 1, 0, 0]]
        blue_offers = [x for x in wholesale_catalog if x.potion_type == [0, 0, 1, 0]]

        # sort by best offers in terms of ml of portion/gold
        red_offers = sorted(red_offers, key=lambda x: x.ml_per_barrel / x.price, reverse=True)
        green_offers = sorted(green_offers, key=lambda x: x.ml_per_barrel / x.price, reverse=True)
        blue_offers = sorted(blue_offers, key=lambda x: x.ml_per_barrel / x.price, reverse=True)


        min_price = min_cat_price(wholesale_catalog) # this hinges on the fact that the min price is not a dark potion for now...

        can_buy_green = True
        can_buy_red = True
        can_buy_blue = True

        while gold > min_price and min_price != -1:
            bought_this_round = False

            if green_ml <= red_ml and green_ml <= blue_ml and can_buy_green or (can_buy_green and not can_buy_blue and not can_buy_red):
                # buy green barrel with best deal that is affordable
                for i in green_offers:
                    if i.price <= gold:
                        wanted_already = check_if_in(i.sku, what_i_want)
                        if wanted_already == -1:
                            what_i_want.append({
                                "sku": i.sku,
                                "quantity": 1
                            })
                        else: #is in what i want
                            what_i_want[wanted_already]["quantity"] = what_i_want[wanted_already]["quantity"] + 1
                        green_ml += i.ml_per_barrel
                        gold -= i.price
                        bought_this_round = True
                        i.quantity = i.quantity - 1
                        break
                if bought_this_round == False:
                    can_buy_green = False

            elif red_ml <= blue_ml and can_buy_red or (can_buy_red and not can_buy_blue and not can_buy_green):
                # buy a red barrel
                for i in red_offers:
                    if i.price <= gold:
                        wanted_already = check_if_in(i.sku, what_i_want)
                        if wanted_already == -1:
                            what_i_want.append({
                                "sku": i.sku,
                                "quantity": 1
                            })
                        else: #is in what i want
                            what_i_want[wanted_already]["quantity"] = what_i_want[wanted_already]["quantity"] + 1
                        red_ml += i.ml_per_barrel
                        gold -= i.price
                        bought_this_round = True
                        i.quantity = i.quantity - 1
                        break
                if bought_this_round == False:
                    can_buy_red = False

            elif can_buy_blue:
                # buy a blue barrel
                for i in blue_offers:
                    if i.price <= gold:
                        wanted_already = check_if_in(i.sku, what_i_want)
                        if wanted_already == -1:
                            what_i_want.append({
                                "sku": i.sku,
                                "quantity": 1
                            })
                        else: #is in what i want
                            what_i_want[wanted_already]["quantity"] = what_i_want[wanted_already]["quantity"] + 1
                        blue_ml += i.ml_per_barrel
                        gold -= i.price
                        bought_this_round = True
                        i.quantity = i.quantity - 1
                        break
                if bought_this_round == False:
                    can_buy_blue = False

            # break out of loop if nothing is affordable that is green or red or blue
            if can_buy_red == False and can_buy_blue == False and can_buy_green == False:
                break

    print(what_i_want) #for debugging

    return what_i_want



def min_cat_price(wholesale_catalog: list[Barrel]):
    min_price = -1
    for i in wholesale_catalog:
        if min_price == -1 or i.price < min_price:
            min_price = i.price

    return min_price


def check_if_in(sku: str, selections):
    for i in range(0, len(selections)):
        if sku == selections[i]["sku"]:
            return i
    return -1