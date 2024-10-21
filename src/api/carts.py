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
    if not customers:
        return [
                    {
                        "success":visited
                    }
                ]   
    level_list = []
    name_list = []
    class_list = []
    for customer in customers:
        level_list.append(customer.level)
        name_list.append(customer.customer_name)
        class_list.append(customer.character_class)
        
    with db.engine.begin() as connection:
        values = [
                    {
                        "visit_id":visit_id, 
                        "level_list":level_list, 
                        "name_list":name_list, 
                        "class_list":class_list
                    }
                ]
        sql_to_execute = """
                            INSERT INTO customer_visits (visit_id, time_id, customer_id) 
                            SELECT :visit_id, (SELECT time.id FROM time ORDER BY id DESC LIMIT 1), customers.id 
                            FROM customers, UNNEST(:level_list, :name_list, :class_list) AS new (level_item, name_item, class_item)
                            WHERE new.level_item = customers.level
                            AND new.name_item = customers.customer_name
                            AND new.class_item = customers.customer_class
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            INSERT INTO customers (level, customer_name, customer_class)
                            SELECT c_customer.c_level, c_customer.c_customer_name, c_customer.c_customer_class 
                            FROM UNNEST(:level_list, :name_list, :class_list)
                            AS c_customer (c_level, c_customer_name, c_customer_class)
                            LEFT JOIN customers AS c
                            ON c.level = c_customer.c_level
                            AND c.customer_name = c_customer.c_customer_name
                            AND c.customer_class = c_customer.c_customer_class
                            WHERE c.level is NULL
                            AND c.customer_name is NULL
                            And c.customer_class is NULL
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        visited = True

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
        sql_to_execute = """
                            INSERT INTO carts (customer_id)
                            SELECT customers.id FROM customers 
                            WHERE customer_name = :customer_name 
                            AND customer_class = :customer_class
                            AND level = :level
                            LIMIT 1
                            RETURNING id
                        """
        values = [
                    {
                        "customer_name": new_cart.customer_name, 
                        "customer_class": new_cart.character_class, 
                        "level": new_cart.level
                    }
                ]
        new_id = connection.execute(sqlalchemy.text(sql_to_execute), values).scalar()
    print("cart_id: %d" % new_id)

    return {"cart_id": new_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ 
    Add item to cart tables and remove item from global inventory
    """
    bought = False
    with db.engine.begin() as connection:
        amt = 0
        sql_to_execute = "SELECT quantity, price FROM potions WHERE sku =:sku LIMIT 1"
        potions = connection.execute(sqlalchemy.text(sql_to_execute), {"sku":item_sku})
        for potion in potions:
            amt = potion.quantity
        if cart_item.quantity <= amt:
            sql_to_execute = "INSERT INTO cart_items (cart_id, sku, potion_quantity) VALUES (:cart_id, :sku, :quantity)"
            values = {
                        "cart_id": cart_id, 
                        "sku": item_sku, 
                        "quantity":cart_item.quantity
                    }
            connection.execute(sqlalchemy.text(sql_to_execute), values)
            bought = True

    return { "success": bought }

class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """
    Remove table and reliqish id for cart, then update gold and potion count
    """
    total_potions = 0
    gold_total = 0
    with db.engine.begin() as connection: 
        sql_to_execute = """
                            INSERT INTO transactions (description, time_id) 
                            VALUES ('CUSTOMER: ' || 
                            (SELECT customer_id FROM carts WHERE id = :cart_id LIMIT 1) ||
                            ' AMOUNT BOUGHT: '|| (SELECT potion_quantity FROM cart_items WHERE cart_id = :cart_id) ||
                            ' TYPE: ' || (SELECT sku FROM cart_items WHERE cart_id= :cart_id) ||
                            ' COST: '|| (SELECT SUM(potion_quantity*(SELECT potions.price FROM potions WHERE potions.sku = cart_items.sku)) FROM cart_items WHERE cart_id = :cart_id), 
                            (SELECT id FROM time ORDER BY id DESC LIMIT 1)) 
                            RETURNING id
                        """
        transaction_id = connection.execute(sqlalchemy.text(sql_to_execute), {"cart_id":cart_id}).scalar()
        sql_to_execute = """
                            INSERT INTO customer_purchases (gold_cost, transaction_id, customer_id, time_id, cart_id) 
                            VALUES (
                                (SELECT SUM(potion_quantity*
                                    (SELECT potions.price FROM potions 
                                    WHERE potions.sku = cart_items.sku)) 
                                FROM cart_items WHERE cart_id = :cart_id), :transaction_id, 
                                (SELECT customer_id FROM carts
                                WHERE id = :cart_id LIMIT 1), 
                                (SELECT time.id FROM time 
                                ORDER BY time.id DESC LIMIT 1),
                                :cart_id
                                )
                        """
        values = [
                    {
                        "cart_id":cart_id,
                        "transaction_id":transaction_id
                    }
                ]
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            UPDATE potions SET quantity = quantity - potion_quantity
                            FROM cart_items AS ci
                            WHERE cart_id = :cart_id
                            AND potions.sku = ci.sku
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            UPDATE global_inventory 
                            SET num_potions = num_potions - (SELECT SUM(potion_quantity) FROM cart_items WHERE cart_id = :cart_id), 
                            gold = gold + (SELECT SUM(potion_quantity*(SELECT potions.price FROM potions WHERE potions.sku = cart_items.sku)) FROM cart_items WHERE cart_id = :cart_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            INSERT INTO potion_ledgers (sku, quantity, time_id, transaction_id)
                            SELECT cart_items.sku, (-1*cart_items.potion_quantity), 
                                (SELECT time.id FROM time ORDER BY time.id DESC LIMIT 1),
                                :transaction_id
                            FROM cart_items
                            WHERE cart_id = :cart_id
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            INSERT INTO gold_ledgers (gold, time_id, transaction_id)
                            VALUES (
                                (SELECT SUM(potion_quantity*(SELECT potions.price FROM potions WHERE potions.sku = cart_items.sku)) FROM cart_items WHERE cart_id = :cart_id), 
                                (SELECT time.id FROM time ORDER BY time.id DESC LIMIT 1), 
                                :transaction_id 
                                )
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        # REPLACE BELOW LATER 
        sql_to_execute = """SELECT 
                            SUM(potion_quantity*
                                (SELECT potions.price FROM potions 
                                WHERE potions.sku = cart_items.sku)) AS gold_total, 
                            SUM(potion_quantity) AS total_potions
                            FROM cart_items WHERE cart_id = :cart_id
                        """
        results = connection.execute(sqlalchemy.text(sql_to_execute), values)
        gold_total = 0
        total_potions = 0
        for result in results:
            gold_total = result.gold_total
            total_potions = result.total_potions
        # REPLACE ABOVE LATER

    return {"total_potions_bought": total_potions, "total_gold_paid": gold_total}
