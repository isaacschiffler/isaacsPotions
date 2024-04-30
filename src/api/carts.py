from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db

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

    json = []

    # figure out what column we're sorting by
    if sort_col is search_sort_options.customer_name:
        sort_by = db.carts.c.name
    elif sort_col is search_sort_options.item_sku:
        sort_by = db.potion_types.c.sku
    elif sort_col is search_sort_options.line_item_total:
        sort_by = (-db.potion_types.c.price * db.potion_ledger.c.quantity)
    elif sort_col is search_sort_options.timestamp:
        sort_by = db.processed.c.created_at
    else:
        # invalid
        assert False


    # generate sql statement for ordering
    if sort_order is search_sort_order.desc:
        # sort ascending
        order_by = sqlalchemy.desc(sort_by)
    elif sort_order is search_sort_order.asc:
        # sort descending
        order_by = sqlalchemy.asc(sort_by)
    else:
        # invalid
        assert False

    # *** quantity will be returned as negative ***
    stmt = (
        sqlalchemy.select(
            db.processed.c.created_at.label("timestamp"),
            db.potion_types.c.name.label("potion_name"),
            db.potion_ledger.c.quantity.label("quantity"),
            db.carts.c.name.label("customer"),
            db.potion_ledger.c.potion_id.label("line_item_id"),
            db.potion_types.c.price.label("price")
        )
        .join(db.carts, db.processed.c.job_id == db.carts.c.id)
        .join(db.potion_ledger, db.processed.c.id == db.potion_ledger.c.trans_id)
        .join(db.potion_types, db.potion_ledger.c.potion_id == db.potion_types.c.id)
        .join(db.gold_ledger, db.processed.c.id == db.gold_ledger.c.trans_id)
        .order_by(order_by)
        .limit(6)
    )

    if search_page != "":
        # configure which page
        stmt = stmt.offset((int(search_page) - 1) * 5)

    if customer_name != "":
        # filter for similar names
        stmt = stmt.where(db.carts.c.name.ilike(f"%{customer_name}%"))

    if potion_sku != "":
        # filter for sku
        stmt = stmt.where(db.potion_types.c.sku.ilike(f"%{potion_sku}%"))

    print(stmt)


    with db.engine.begin() as connection:
        result = connection.execute(stmt)
        i = 0  # counter to see if there is enough for another page
        for row in result:
            i += 1
            json.append({
                "line_item_id": row.line_item_id,
                "item_sku": str(-row.quantity) + " " + row.potion_name,
                "customer_name": row.customer,
                "line_item_total": row.price * -row.quantity,
                "timestamp": row.timestamp
            })

    # configure page stuff
    if i > 5:
        another_page = True
    else:
        another_page = False

    page = 1 if search_page == "" else int(search_page)  # get page number from search_page parameter

    if page == 1:
        # no previous page for sure because we are at first page
        previous = ""
    elif page > 1:
        previous = "https://isaacspotions.onrender.com/carts/search/?search_page=" + str(page - 1) + "&sort_col=" + sort_col + "&sort_order=" + sort_order
    else:
        print("Not a valid page..." + str(page))

    if another_page:
        # there is at least one more page of data
        next = "https://isaacspotions.onrender.com/carts/search/?search_page=" + str(page + 1) + "&sort_col=" + sort_col + "&sort_order=" + sort_order
    else:
        next = ""

    return {
        "previous": previous,
        "next": next,
        "results": json,
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
    with db.engine.begin() as connection:
        
        id = connection.execute(sqlalchemy.text("INSERT INTO carts (name, class, level) VALUES (:name, :class, :level) returning id;"),
                                    {
                                        'name': new_cart.customer_name,
                                        'class': new_cart.character_class,
                                        'level': new_cart.level
                                    }).fetchone()[0]

        print("Cart: " + str(id) + " " + new_cart.customer_name + " " + new_cart.character_class + " " + str(new_cart.level))

    return {"cart_id": id} # trying to return cart_id as an int instead to hopefully resolve an error?


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ add quantity of items """
    # inserted = False
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("""
                                            INSERT INTO cart_items (cart_id, potion_id, quantity, price) 
                                            SELECT :cart_id, potion_types.id, :quantity, potion_types.price
                                            FROM potion_types 
                                            WHERE potion_types.sku = :item_sku"""),
                            {
                                'cart_id': cart_id,
                                'quantity': cart_item.quantity,
                                'item_sku': item_sku
                            })
        print("new entry made in cart " + str(cart_id))

    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """Subtract potions and add gold"""

    with db.engine.begin() as connection:
        # insert into processed
        trans_id = connection.execute(sqlalchemy.text("""INSERT INTO processed
                                                     (job_id, type) VALUES
                                                     (:job_id, 'potion_sale') returning id;
                                                      """),
                                                    [{
                                                        'job_id': cart_id
                                                    }]).fetchone()[0]

        # update potion_ledger
        connection.execute(sqlalchemy.text("""INSERT INTO potion_ledger
                                           (trans_id, quantity, potion_id)
                                           SELECT :trans_id, -1 * quantity, potion_id
                                           FROM cart_items
                                           WHERE cart_items.cart_id = :cart_id;
                                           """),
                                           [{
                                               'trans_id': trans_id,
                                               'cart_id': cart_id
                                           }])
        
        # update gold_ledger
        connection.execute(sqlalchemy.text("""INSERT INTO gold_ledger
                                           (trans_id, gold)
                                           SELECT :trans_id, SUM(quantity * price)
                                           FROM cart_items
                                           WHERE cart_items.cart_id = :cart_id
                                           GROUP BY cart_items.cart_id;
                                           """),
                                           [{
                                               'trans_id': trans_id,
                                               'cart_id': cart_id
                                           }])
        
        # get quantity of potions sold
        quant_bought = connection.execute(sqlalchemy.text("SELECT SUM(quantity) FROM potion_ledger WHERE trans_id = :trans_id"),
                                          [{
                                              'trans_id': trans_id
                                          }]).fetchone()[0] * -1
        # get gold paid
        income = connection.execute(sqlalchemy.text("SELECT gold FROM gold_ledger WHERE trans_id = :trans_id"),
                                    [{
                                        'trans_id': trans_id
                                    }]).fetchone()[0]
    print("potions bought: " + str(quant_bought) + " gold paid: " + str(income))
    

    return {"total_potions_bought": quant_bought, "total_gold_paid": income}
