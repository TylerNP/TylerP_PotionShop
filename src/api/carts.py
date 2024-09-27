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

    return [
            {
                "success":True
            }
    ]


@router.post("/")
def create_cart(new_cart: Customer):
    """ """

    with db.engine.begin() as connection: 
        curr_ids = connection.execute(sqlalchemy.text("SELECT cart_id FROM carts"))
        new_id = 0
        for ids in curr_ids:
            if int(ids.cart_id) == new_id:
                new_id += 1
            else:
                break

        connection.execute(sqlalchemy.text(f"INSERT INTO carts (cart_id, total_potions) VALUES ('{new_id}', 0)"))
        connection.execute(sqlalchemy.text(f"CREATE TABLE cart_number_{new_id} (id bigint generated always as identity, potion_name text, potion_quantity int)"))

    return [{"cart_id": new_id}]


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(f"INSERT INTO cart_number_{cart_id} (potion_name, potion_quantity) VALUES ('{item_sku}', {cart_item.quantity})"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_{item_sku}_potions = num_{item_sku}_potions - {cart_item.quantity}"))
        connection.execute(sqlalchemy.text(f"UPDATE carts SET total_potions = total_potions + {cart_item.quantity} WHERE cart_id = '{cart_id}' "))

    return { "quantity": cart_item.quantity }


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    cnt = 0
    with db.engine.begin() as connection: 
        total = connection.execute(sqlalchemy.text(f"SELECT total_potions FROM carts WHERE cart_id = '{cart_id}'")).scalar()
        if total > 0:
            potions = connection.execute(sqlalchemy.text(f"SELECT potion_quantity FROM cart_number_{cart_id}"))
            for item in potions:
                cnt += item.potion_quantity
        connection.execute(sqlalchemy.text(f"DROP TABLE cart_number_{cart_id}"))
        connection.execute(sqlalchemy.text(f"DELETE FROM carts WHERE cart_id = '{cart_id}'"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold + {int(cart_checkout.payment)}"))


    return {"total_potions_bought": cnt, "total_gold_paid": int(cart_checkout.payment)}
