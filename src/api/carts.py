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
    visited = False
    with db.engine.begin() as connection:
        for customer in customers:
            sql_to_execute = "SELECT 1 FROM customers WHERE (level = %d AND customer_name = '%s' AND customer_class = '%s') LIMIT 1"
            found = connection.execute(sqlalchemy.text(sql_to_execute % (customer.level, customer.customer_name, customer.character_class))).scalar()
            if found == 1:
                sql_to_execute = "UPDATE customers SET visit_id = %d WHERE (level = %d AND customer_name = '%s' AND customer_class = '%s')"
            else:
                sql_to_execute = "INSERT INTO customers (visit_id, level, customer_name, customer_class) VALUES (%d, %d, '%s', '%s')"
            connection.execute(sqlalchemy.text(sql_to_execute % (visit_id, customer.level, customer.customer_name, customer.character_class)))
            visited = True
    print(customers)

    return [
            {
                "success":visited
            }
    ]


@router.post("/")
def create_cart(new_cart: Customer):
    """
    Issue a unique id for carts and new table for cart inventory 
    """
    new_id = 0
    with db.engine.begin() as connection: 
        curr_ids = connection.execute(sqlalchemy.text("SELECT cart_id FROM carts"))
        for ids in curr_ids:
            if int(ids.cart_id) == new_id:
                new_id += 1
            else:
                break

        sql_to_execute = "INSERT INTO carts (cart_id) VALUES (%d)"
        connection.execute(sqlalchemy.text(sql_to_execute % new_id))
        sql_to_execute = "UPDATE customers SET cart_id = '%d' WHERE (customer_name = '%s' AND customer_class = '%s' AND level = %d)"
        connection.execute(sqlalchemy.text(sql_to_execute % (new_id, new_cart.customer_name, new_cart.character_class, new_cart.level)))
    print("cart_id: %d" % new_id)

    return {"cart_id": "%s" % new_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ 
    Add item to cart tables and remove item from global inventory
    """
    bought = False
    with db.engine.begin() as connection:
        sql_to_execute = "SELECT quantity FROM potions WHERE sku = %s LIMIT 1"
        amt = connection.execute(sqlalchemy.text(sql_to_execute % item_sku))
        if cart_item <= amt:
            sql_to_execute = "INSERT INTO cart_items (cart_id, sku, potion_quantity) VALUES ('%d', '%s', %d)"
            connection.execute(sqlalchemy.text(sql_to_execute % (cart_id, item_sku, cart_item.quantity)))
            bought = True

    return { "success": bought }


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """
    Remove table and reliqish id for cart, then update gold and potion count
    """
    gold_total = 0
    total_potions = 0
    with db.engine.begin() as connection: 
        sql_to_execute = "SELECT potion_quantity, sku FROM cart_items WHERE cart_id = '%s'"
        potions = connection.execute(sqlalchemy.text(sql_to_execute % cart_id))
        for item in potions:
            sql_to_execute = "SELECT price FROM potions WHERE sku = '%s'"
            price = connection.execute(sqlalchemy.text(sql_to_execute % item.sku)).scalar() 
            gold_total += item.potion_quantity * price
            total_potions += item.potion_quantity
            sql_to_execute = "UPDATE potions SET quantity = quantity - %d WHERE sku = '%s'"
            connection.execute(sqlalchemy.text(sql_to_execute % (item.potion_quantity, item.sku)))
            sql_to_execute = "UPDATE global_inventory SET num_potions = num_potions - %d"
            connection.execute(sqlalchemy.text(sql_to_execute % item.potion_quantity))

        sql_to_execute = "DELETE FROM carts WHERE cart_id = '%d'"
        connection.execute(sqlalchemy.text(sql_to_execute % cart_id))
        sql_to_execute = "UPDATE global_inventory SET gold = gold + %d"
        connection.execute(sqlalchemy.text(sql_to_execute % gold_total))
        print(cart_checkout.payment)

    return {"total_potions_bought": total_potions, "total_gold_paid": gold_total}
