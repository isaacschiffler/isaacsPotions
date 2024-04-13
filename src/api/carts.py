from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db
import uuid

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   

@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """

    return {
        "previous": "",
        "next": "",
        "results": [
            {
                "line_item_id": 1,
                "item_sku": "1 oblivion potion",
                "customer_name": "Scaramouche",
                "line_item_total": 50,
                "timestamp": "2021-01-01T00:00:00Z",
            }
        ],
    }


class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int

@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Which customers visited the shop today?
    """
    print(customers)

    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """ create a new cart for the given customer """
    # do carts persist through to customer revisiting?
    # aka, will a customer call create_cart if they already have a cart?
    #      if so, make sure to check for existence before inserting a new on in!
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("INSERT INTO carts (name, class, level) VALUES (:name, :class, :level);"),
                                    {
                                        'name': new_cart.customer_name,
                                        'class': new_cart.character_class,
                                        'level': new_cart.level
                                    })
        result = connection.execute(sqlalchemy.text("SELECT id FROM carts WHERE name = :name AND class = :class AND level = :level;"),
                                    {
                                        'name': new_cart.customer_name,
                                        'class': new_cart.character_class,
                                        'level': new_cart.level
                                    })
        id = result.fetchone()[0]

        print("New cart: " + str(id) + " " + new_cart.customer_name + " " + new_cart.character_class + " " + str(new_cart.level))

    return {"cart_id": str(id)}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ add quantity of items """
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM cart_items WHERE cart_id = :cart_id AND item_sku = :item_sku;"),
                                    {
                                        'cart_id': cart_id,
                                        'item_sku': item_sku
                                    })
        row = result.fetchone()
        if row:
            # row exists, update quantity
            new_quant = cart_item + row[2]
            connection.execute(sqlalchemy.text("UPDATE cart_items SET quantity = :quantity WHERE cart_id = :cart_id AND item_sku = :item_sku;"),
                               {
                                   'quantity': new_quant,
                                   'cart_id': cart_id,
                                   'item_sku': item_sku
                               })
        else:
            # row doesn't exist, insert
            connection.execute(sqlalchemy.text("INSERT INTO cart_items (cart_id, item_sku, quantity) VALUES (:cart_id, :item_sku, :quantity)"),
                               {
                                   'cart_id': cart_id,
                                   'item_sku': item_sku,
                                   'quantity': cart_item.quantity
                               })

    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    #subtract potions and add gold
    """ """

    with db.engine.begin() as connection:
        cart_items = connection.execute(sqlalchemy.text("SELECT * FROM cart_items WHERE cart_id = :cart_id"),
                                    {
                                        'cart_id': cart_id
                                    })
        income = 0
        potions_bought = 0
        for row in cart_items:
            sku = row[1]
            quant_bought = row[2]
            potion = connection.execute(sqlalchemy.text("SELECT quantity, price FROM potion_inventory where sku = :sku"),
                                        {
                                            'sku': sku
                                        })
            potion = potion.fetchone()
            num_potions_held = potion[0]
            price_for_potion = potion[1]
            income += price_for_potion * quant_bought
            potions_bought += quant_bought

            # update number of potions in inventory
            connection.execute(sqlalchemy.text("UPDATE potion_inventory SET quantity = :quantity WHERE sku = :sku"),
                               {
                                   'quantity': num_potions_held - quant_bought,
                                   'sku': sku
                               })

        # update gold with income
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        globe = result.fetchone()
        gold = globe[1]
        connection.execute(sqlalchemy.text(""" 
                                    UPDATE global_inventory
                                    SET gold = :gold
                                    WHERE id = 1;
                                    """),
                                    {'gold': gold + income})
        
        # delete the cart from carts and cart_items
        connection.execute(sqlalchemy.text("DELETE FROM carts where id = :cart_id"),
                           {
                               'cart_id': cart_id
                           })
        connection.execute(sqlalchemy.text("DELETE FROM cart_items where cart_id = :cart_id"),
                           {
                               'cart_id': cart_id
                           })

    return {"total_potions_bought": quant_bought, "total_gold_paid": income}
