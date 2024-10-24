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
                            WITH popular (sku) AS (
                            SELECT potions.sku
                            FROM potions, (
                                SELECT part.sku AS sku
                                FROM (
                                    SELECT potions.sku,
                                        SUM(-1*potion_ledgers.quantity) AS amt 
                                    FROM potions, potion_ledgers, transactions, ( 
                                        SELECT time.id AS id
                                        FROM time
                                        WHERE time.day = (
                                            SELECT time.day 
                                            FROM time 
                                            ORDER BY time.id DESC 
                                            LIMIT 1
                                        )
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
                        )

                        (SELECT potions.sku, potions.quantity, potions.price, potions.red, potions.green, potions.blue, potions.dark, potions.name
                        FROM potions
                        WHERE NOT EXISTS (SELECT popular.sku FROM popular WHERE popular.sku = potions.sku)
                        AND quantity > 0
                        ORDER BY quantity 
                        LIMIT 6-(SELECT COUNT(1) FROM popular))
                        UNION ALL
                        (SELECT potions.sku, potions.quantity, potions.price, potions.red, potions.green, potions.blue, potions.dark, potions.name 
                        FROM potions, popular
                        WHERE potions.sku = popular.sku)
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
