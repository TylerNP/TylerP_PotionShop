from fastapi import APIRouter

import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    potions_available = []
    with db.engine.begin() as connection: 
        sql_to_execute = """
                            SELECT sku, quantity, price, red, green, blue, dark, name 
                            FROM potions 
                            WHERE quantity > 0
                            ORDER BY quantity DESC 
                            LIMIT 6
                        """
        sql_to_execute = """
                            SELECT potions.sku, potions.quantity, potions.price, potions.red, potions.green, potions.blue, potions.dark, potions.name
                            FROM potions, (
                                SELECT part.sku 
                                FROM (
                                    SELECT potions.sku,
                                        SUM(-1*potion_ledgers.quantity) AS amt 
                                    FROM potions, potion_ledgers, transactions, ( 
                                        SELECT time.id AS id
                                        FROM time
                                        WHERE time.day = (SELECT time.day FROM time ORDER BY time.id DESC LIMIT 1)
                                        ORDER BY time.id DESC
                                        LIMIT 12
                                        OFFSET 1
                                    ) AS time_filtered 
                                    WHERE potions.sku = potion_ledgers.sku 
                                    AND potion_ledgers.transaction_id = transactions.id 
                                    AND potion_ledgers.quantity < 0 
                                    AND transactions.time_id = time_filtered.id
                                    GROUP BY potions.sku
                                ) AS part
                                ORDER BY part.amt DESC
                            ) AS sold
                            WHERE potions.sku = sold.sku
                            AND quantity > 0
                            ORDER BY quantity DESC
                            LIMIT 6
                        """
        
        potions = connection.execute(sqlalchemy.text(sql_to_execute))
        for potion in potions:
            potions_available.append(
                {
                    "sku": potion.sku,
                    "name": potion.name,
                    "quantity": potion.quantity,
                    "price": potion.price,
                    "potion_type": [potion.red, potion.green, potion.blue, potion.dark]
                } 
            )
    print(potions_available)
    return potions_available
