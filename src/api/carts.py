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
    level_list = []
    name_list = []
    class_list = []
    print(customers)
    if not customers:
        return [
            {
                "success":visited
            }
    ]
    for customer in customers:
        level_list.append(customer.level)
        name_list.append(customer.customer_name)
        class_list.append(customer.character_class)
        
    with db.engine.begin() as connection:
        sql_to_execute = """
                            CREATE TABLE current_customers (
                            new_visit_id bigint null,
                            c_level bigint null,
                            c_customer_name text null,
                            c_customer_class text null
                            )
                        """
        connection.execute(sqlalchemy.text(sql_to_execute))
        sql_to_execute = """
                            INSERT INTO current_customers (new_visit_id, c_level, c_customer_name, c_customer_class)
                            SELECT :visit_id, parameter.p_level, parameter.p_customer_name, parameter.p_customer_class 
                            FROM UNNEST(:level_list, :name_list, :class_list)
                            AS parameter (p_level, p_customer_name, p_customer_class)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), [{"visit_id":visit_id, "level_list":level_list, "name_list":name_list, "class_list":class_list}])
        sql_to_execute = """
                            INSERT INTO customers (visit_id, level, customer_name, customer_class)
                            SELECT new_visit_id, c_level, c_customer_name, c_customer_class
                            FROM current_customers AS cc
                            LEFT JOIN customers AS c
                            ON c.level = cc.c_level
                            AND c.customer_name = cc.c_customer_name
                            AND c.customer_class = cc.c_customer_class
                            WHERE c.level is NULL
                            AND c.customer_name is NULL
                            And c.customer_class is NULL
                        """
        connection.execute(sqlalchemy.text(sql_to_execute))
        sql_to_execute = """
                            UPDATE customers 
                            SET visit_id = cc.new_visit_id
                            FROM current_customers AS cc
                            WHERE level = cc.c_level
                            AND customer_name = cc.c_customer_name
                            AND customer_class = cc.c_customer_class
                        """
        connection.execute(sqlalchemy.text(sql_to_execute))
        connection.execute(sqlalchemy.text("DROP TABLE current_customers"))
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
        new_id = connection.execute(sqlalchemy.text("INSERT INTO carts DEFAULT VALUES RETURNING id")).scalar()
        sql_to_execute = """
                            UPDATE customers SET cart_id = :cart_id
                            WHERE customer_name = :customer_name 
                            AND customer_class = :customer_class
                            AND level = :level
                        """
        values = [
                    {
                        "cart_id": new_id, 
                        "customer_name": new_cart.customer_name, 
                        "customer_class": new_cart.character_class, 
                        "level": new_cart.level
                    }
                ]
        connection.execute(sqlalchemy.text(sql_to_execute), values)
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
        price = 0
        sql_to_execute = "SELECT quantity, price FROM potions WHERE sku =:sku LIMIT 1"
        potions = connection.execute(sqlalchemy.text(sql_to_execute), {"sku":item_sku})
        for potion in potions:
            amt = potion.quantity
            price = int(potion.price)
        if cart_item.quantity <= amt:
            sql_to_execute = "INSERT INTO cart_items (cart_id, sku, potion_quantity) VALUES (:cart_id, :sku, :quantity)"
            values = [
                        {
                            "cart_id": cart_id, 
                            "sku": item_sku, 
                            "quantity":cart_item.quantity
                        }
                    ]
            connection.execute(sqlalchemy.text(sql_to_execute), values)
            sql_to_execute = """
                                INSERT INTO customer_ledgers (gold_cost, cart_id, customer_id) 
                                VALUES (:gold_cost, :cart_id, (SELECT id FROM customers WHERE cart_id = :cart_id))
                            """
            values = [
                        {
                            "gold_cost": cart_item.quantity*price, 
                            "cart_id":cart_id
                        }
                    ]
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
                            UPDATE potions SET quantity = quantity - potion_quantity
                            FROM cart_items AS ci
                            WHERE cart_id = :cart_id
                            AND potions.sku = ci.sku
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), [{"cart_id":cart_id}])
        sql_to_execute = """
                            UPDATE global_inventory 
                            SET num_potions = num_potions - (SELECT SUM(potion_quantity) FROM cart_items WHERE cart_id = :cart_id), 
                            gold = gold + (SELECT SUM(gold_cost) FROM customer_ledgers WHERE cart_id = :cart_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), {"cart_id":cart_id})

        sql_to_execute = """
                                INSERT INTO gold_transactions (description, time_id) 
                                VALUES ('CUSTOMER: ' || (SELECT id FROM customers WHERE cart_id = :cart_id LIMIT 1) ||
                                ' AMOUNT BOUGHT: '|| (SELECT potion_quantity FROM cart_items WHERE cart_id = :cart_id) ||
                                ' TYPE: ' || (SELECT sku FROM cart_items WHERE cart_id = :cart_id) ||
                                ' COST: '|| (SELECT SUM(gold_cost) FROM customer_ledgers WHERE cart_id = :cart_id), 
                                (SELECT id FROM time ORDER BY id DESC LIMIT 1)) 
                                RETURNING id
                            """
        transaction_id = connection.execute(sqlalchemy.text(sql_to_execute), {"cart_id":cart_id}).scalar()
        # REPLACE BELOW LATER 
        sql_to_execute = "UPDATE customer_ledgers SET transaction_id = :id WHERE cart_id = :cart_id"
        connection.execute(sqlalchemy.text(sql_to_execute), {"cart_id":cart_id, "id":transaction_id})
        sql_to_execute = "SELECT SUM(gold_cost) FROM customer_ledgers WHERE cart_id = :cart_id"
        gold_total = connection.execute(sqlalchemy.text(sql_to_execute), {"cart_id":cart_id}).scalar()
        sql_to_execute = "SELECT SUM(potion_quantity) FROM cart_items WHERE cart_id = :cart_id"
        total_potions = connection.execute(sqlalchemy.text(sql_to_execute), [{"cart_id":cart_id}]).scalar()
        # REPLACE ABOVE LATER
        sql_to_execute = "DELETE FROM carts WHERE id = :id"
        connection.execute(sqlalchemy.text(sql_to_execute), {"id":cart_id})

    return {"total_potions_bought": total_potions, "total_gold_paid": gold_total}
