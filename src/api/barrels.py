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
        print(f"Current database status:  {str(globe.gold)} {str(globe.num_red_ml)}  {str(globe.num_green_ml)} {str(globe.num_blue_ml)} {str(globe.num_dark_ml)}") #for debugging
        gold = globe.gold
        num_red_ml = globe.num_red_ml
        num_green_ml = globe.num_green_ml
        num_blue_ml = globe.num_blue_ml
        num_dark_ml = globe.num_dark_ml
        new_green = 0
        new_red = 0
        new_blue = 0
        new_dark = 0
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
            elif type == [0, 0, 0, 1]: # if a dark barrel
                new_dark += ml * quantity
            else: # not green, red, blue, or dark
                print("potion delivered that is not red, green, blue, or dark.......")
            cost += price * quantity
            

        # connection.execute(sqlalchemy.text("""
        #                                 UPDATE global_inventory
        #                                 SET num_green_ml = :green, gold = :gold, num_red_ml = :red, num_blue_ml = :blue, num_dark_ml = :dark
        #                                 WHERE id = 1;
        #                                 """),  
        #                                 {'green': new_green + num_green_ml, 
        #                                  'gold': gold - cost, 
        #                                  'red': new_red + num_red_ml, 
        #                                  'blue': new_blue + num_blue_ml,
        #                                  'dark': new_dark + num_dark_ml})
            
        
                
        # add barrel order to processed
        trans_id = connection.execute(sqlalchemy.text("""INSERT INTO processed
                                           (job_id, type) VALUES
                                           (:job_id, 'barrel') returning id;"""),
                                           [{
                                               'job_id': order_id
                                           }]).fetchone()[0]
        
        # add order to barrel_ledger
        connection.execute(sqlalchemy.text("""INSERT INTO barrel_ledger
                                           (trans_id, red_ml, green_ml, blue_ml, dark_ml) VALUES
                                           (:trans_id, :new_red, :new_green, :new_blue, :new_dark);"""), 
                                           [{
                                               'trans_id': trans_id,
                                               'new_red': new_red,
                                               'new_green': new_green,
                                               'new_blue': new_blue,
                                               'new_dark': new_dark
                                           }])
        
        # add order to gold_ledger
        connection.execute(sqlalchemy.text("""INSERT INTO gold_ledger
                                           (trans_id, gold) VALUES
                                           (:trans_id, :cost);
                                           """), 
                                           [{
                                               'trans_id': trans_id,
                                               'cost': -cost
                                           }])
        
    print(f"BARREL DELIVERY - gold paid: {cost} red_ml: {new_red} green_ml: {new_green} blue_ml: {new_blue} dark_ml: {new_dark}")

    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)

    what_i_want = []

    with db.engine.begin() as connection:
        # get global inventory info from the ledgers through the globe view
        globe = connection.execute(sqlalchemy.text("SELECT * from globe")).fetchone()

        # out-dated code????
        # g_inventory = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        # globe = g_inventory.fetchone()
        print(f"Current database status: {str(globe.gold)} {str(globe.red_ml)} {str(globe.green_ml)} {str(globe.blue_ml)} {str(globe.dark_ml)}")
        gold = globe.gold
        capacity = globe.ml_capacity
        ml_count = globe.red_ml + globe.green_ml + globe.blue_ml + globe.dark_ml

        # get catalog offerings for each color barrel
        red_offers = [x for x in wholesale_catalog if x.potion_type == [1, 0, 0, 0]]
        green_offers = [x for x in wholesale_catalog if x.potion_type == [0, 1, 0, 0]]
        blue_offers = [x for x in wholesale_catalog if x.potion_type == [0, 0, 1, 0]]
        dark_offers = [x for x in wholesale_catalog if x.potion_type == [0, 0, 0, 1]]

        # sort by best offers in terms of ml of potion/gold
        red_offers = sorted(red_offers, key=lambda x: x.ml_per_barrel / x.price, reverse=True)
        green_offers = sorted(green_offers, key=lambda x: x.ml_per_barrel / x.price, reverse=True)
        blue_offers = sorted(blue_offers, key=lambda x: x.ml_per_barrel / x.price, reverse=True)
        dark_offers = sorted(dark_offers, key=lambda x: x.ml_per_barrel / x.price, reverse=True)

        min_price = min_cat_price(wholesale_catalog)

        total_barrels_offered = 0
        for i in wholesale_catalog:
            total_barrels_offered += i.quantity

        barrels_bought = 0

        red_ml = 0
        green_ml = 0
        blue_ml = 0
        dark_ml = 0
        cost = 0

        while red_ml < capacity / 4:
            # try to buy best offer barrel
            bought = False
            for i in red_offers:
                if try_to_buy(i, gold, what_i_want, ml_count, capacity) == True:
                    gold -= i.price
                    barrels_bought += 1

                    red_ml += i.ml_per_barrel
                    ml_count += i.ml_per_barrel
                    cost += i.price
                    bought = True
                    break
            if bought == False:
                break

        while green_ml < capacity / 4:
            # try to buy best offer barrel
            bought = False
            for i in green_offers:
                if try_to_buy(i, gold, what_i_want, ml_count, capacity) == True:
                    gold -= i.price
                    barrels_bought += 1

                    green_ml += i.ml_per_barrel
                    ml_count += i.ml_per_barrel
                    cost += i.price
                    bought = True
                    break
            if bought == False:
                break

        while blue_ml < capacity / 4:
            # try to buy best offer barrel
            bought = False
            for i in blue_offers:
                if try_to_buy(i, gold, what_i_want, ml_count, capacity) == True:
                    gold -= i.price
                    barrels_bought += 1

                    blue_ml += i.ml_per_barrel
                    ml_count += i.ml_per_barrel
                    cost += i.price
                    bought = True
                    break
            if bought == False:
                break

        while dark_ml < capacity / 4:
            # try to buy best offer barrel
            bought = False
            for i in dark_offers:
                if try_to_buy(i, gold, what_i_want, ml_count, capacity) == True:
                    gold -= i.price
                    barrels_bought += 1

                    dark_ml += i.ml_per_barrel
                    ml_count += i.ml_per_barrel
                    cost += i.price
                    bought = True
                    break
            if bought == False:
                break
        # # basically cycle through the catalog and buy the best deal for each color if 
        # # i can afford it until i don't have enough gold for anything or i bought all barrels
        # # MAKE THIS MORE EFFICIENT!!!!!!!!!-------------------------------------------------------------------------------
        # while gold >= min_price and min_price != -1 and barrels_bought < total_barrels_offered and ml_count < capacity:
        #     # try to buy one red barrel
        #     for i in red_offers:
        #         if try_to_buy(i, gold, what_i_want, ml_count, capacity) == True:
        #             gold -= i.price
        #             barrels_bought += 1

        #             red_ml += i.ml_per_barrel
        #             cost += i.price
        #             break
            
        #     # try to buy one green barrel
        #     for i in green_offers:
        #         if try_to_buy(i, gold, what_i_want, ml_count, capacity) == True:
        #             gold -= i.price
        #             barrels_bought += 1

        #             green_ml += i.ml_per_barrel
        #             cost += i.price
        #             break

        #     # try to buy one blue barrel
        #     for i in blue_offers:
        #         if try_to_buy(i, gold, what_i_want, ml_count, capacity) == True:
        #             gold -= i.price
        #             barrels_bought += 1

        #             blue_ml += i.ml_per_barrel
        #             cost += i.price
        #             break

        #     # try to buy one dark barrel
        #     for i in dark_offers:
        #         if try_to_buy(i, gold, what_i_want, ml_count, capacity) == True:
        #             gold -= i.price
        #             barrels_bought += 1

        #             dark_ml += i.ml_per_barrel
        #             cost += i.price
        #             break

    print(what_i_want) #for debugging

    return what_i_want


'''This function finds the minimum price in the barrel catalog'''
def min_cat_price(wholesale_catalog: list[Barrel]):
    min_price = -1 # default min_price is -1 if no barrels are offered
    for i in wholesale_catalog:
        if min_price == -1 or i.price < min_price:
            min_price = i.price

    return min_price


'''This function checkes to see if the given sku is already in the purchase plan'''
def check_if_in(sku: str, selections):
    for i in range(0, len(selections)):
        if sku == selections[i]["sku"]:
            return i
        
    return -1

'''This function checks to see if we can buy the given barrel. 
If we can, it adds it to the plan and returns True, returns False if not'''
def try_to_buy(barrel: Barrel, gold, what_i_want, ml_count, capacity):
    if barrel.price <= gold and barrel.quantity > 0 and ml_count + barrel.ml_per_barrel <= capacity:
        wanted_already = check_if_in(barrel.sku, what_i_want)
        if wanted_already == -1:
            what_i_want.append({
                "sku": barrel.sku,
                "quantity": 1
            })
        else: #is in what i want
            what_i_want[wanted_already]["quantity"] = what_i_want[wanted_already]["quantity"] + 1
        barrel.quantity = barrel.quantity - 1
        return True
    
    return False
