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
        # first check to see if customer already has a cart
        check = connection.execute(sqlalchemy.text("SELECT id FROM carts WHERE name = :name AND class = :class AND level = :level;"),
                                    {
                                            'name': new_cart.customer_name,
                                            'class': new_cart.character_class,
                                            'level': new_cart.level
                                    })
        exist = check.fetchone()
        
        if not exist:
            result = connection.execute(sqlalchemy.text("INSERT INTO carts (name, class, level) VALUES (:name, :class, :level) returning id;"),
                                        {
                                            'name': new_cart.customer_name,
                                            'class': new_cart.character_class,
                                            'level': new_cart.level
                                        })
            id = result.fetchone()[0]
        else:
            id = exist.id

        print("Cart: " + str(id) + " " + new_cart.customer_name + " " + new_cart.character_class + " " + str(new_cart.level))

    return {"cart_id": id} # trying to return cart_id as an int instead to hopefully resolve an error?


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ add quantity of items """
    inserted = False
    with db.engine.begin() as connection:
        try:
            # row doesn't exist, insert
            connection.execute(sqlalchemy.text("""
                                               INSERT INTO cart_items (cart_id, potion_id, quantity, price) 
                                               SELECT :cart_id, potion_inventory.id, :quantity, potion_inventory.price
                                               FROM potion_inventory 
                                               WHERE potion_inventory.sku = :item_sku"""),
                               {
                                   'cart_id': cart_id,
                                   'quantity': cart_item.quantity,
                                   'item_sku': item_sku
                               })
            print("new entry made")
            inserted = True
        except sqlalchemy.exc.IntegrityError:
            connection.rollback()
            print("entry already in; customer updating quantity")
    if not inserted:
        with db.engine.begin() as connection:
            result = connection.execute(sqlalchemy.text("""UPDATE cart_items 
                                                SET quantity = cart_items.quantity + :quantity 
                                                FROM potion_inventory
                                                WHERE cart_items.cart_id = :cart_id 
                                                AND cart_items.potion_id = potion_inventory.id 
                                                AND potion_inventory.sku = :item_sku;
                                                """),
                                {
                                    'quantity': cart_item.quantity,
                                    'cart_id': cart_id,
                                    'item_sku': item_sku
                                })
            print("updating existing entry")
            print(result)

    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    #subtract potions and add gold
    """ """

    with db.engine.begin() as connection:
        # update potion quantity levels
        quant_bought = connection.execute(sqlalchemy.text("""
                                        UPDATE potion_inventory 
                                        SET quantity = potion_inventory.quantity - cart_items.quantity
                                        FROM cart_items
                                        WHERE potion_inventory.id = cart_items.potion_id and cart_items.cart_id = :cart_id
                                        returning cart_items.quantity as quant_bought;
                                        """), { 'cart_id': cart_id})
        # update global gold levels
        income = connection.execute(sqlalchemy.text("""
                                        UPDATE global_inventory 
                                        SET gold = global_inventory.gold + (cart_items.quantity * cart_items.price)
                                        FROM cart_items, potion_inventory
                                        WHERE potion_inventory.id = cart_items.potion_id and cart_items.cart_id = :cart_id
                                        returning cart_items.quantity * cart_items.price as income;
                                        """), { 'cart_id': cart_id})
        
        quant_bought = quant_bought.fetchone()
        income = income.fetchone()

        if quant_bought and income:
            # no erros in updating
            quant_bought = quant_bought[0]
            income = income[0]
        else:
            print("error updating...")
        
        # delete the cart from carts and cart_items
        connection.execute(sqlalchemy.text("DELETE FROM cart_items where cart_id = :cart_id"),
                           {
                                'cart_id': cart_id
                            })
        connection.execute(sqlalchemy.text("DELETE FROM carts where id = :cart_id"),
                           {
                               'cart_id': cart_id
                           })
        
    

    return {"total_potions_bought": quant_bought, "total_gold_paid": income}
