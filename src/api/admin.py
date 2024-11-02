from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth

import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """
    with db.engine.begin() as connection:
        sql_to_execute = """
                            UPDATE global_inventory 
                            SET gold = 100, 
                            num_red_ml = 0,
                            num_green_ml = 0,
                            num_blue_ml = 0,
                            num_dark_ml = 0,
                            num_potions = 0,
                            ml_capacity = 1,
                            potion_capacity = 1
                        """
        connection.execute(sqlalchemy.text(sql_to_execute)) 
        #sql_to_execute = "TRUNCATE carts"
        #connection.execute(sqlalchemy.text(sql_to_execute))
        sql_to_execute = "UPDATE potions SET quantity = 0"
        connection.execute(sqlalchemy.text(sql_to_execute))
        sql_to_execute = """
                            INSERT INTO transactions (description, time_id) 
                            VALUES ('RESET',(SELECT MAX(time.id) FROM time LIMIT 1)) 
                            RETURNING id
                        """
        transaction_id = connection.execute(sqlalchemy.text(sql_to_execute)).scalar()
        values = {"transaction_id":transaction_id}
        sql_to_execute = """
                            WITH potion_adjust AS (
                                SELECT 
                                    potion_ledgers.sku, 
                                    -1*SUM(potion_ledgers.quantity) AS reset_amount
                                FROM 
                                    potion_ledgers 
                                GROUP BY 
                                    potion_ledgers.sku
                            )

                            INSERT INTO 
                            potion_ledgers (sku, quantity, transaction_id) 
                            (SELECT sku, reset_amount, :transaction_id FROM potion_adjust);
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            WITH ml_adjust AS (
                            SELECT
                                -1*SUM(ml_ledgers.num_red_ml) AS red,
                                -1*SUM(ml_ledgers.num_green_ml) AS green,
                                -1*SUM(ml_ledgers.num_blue_ml) AS blue,
                                -1*SUM(ml_ledgers.num_dark_ml) AS dark
                            FROM
                                ml_ledgers 
                            )

                            INSERT INTO 
                            ml_ledgers (num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, transaction_id) 
                            (SELECT red,green,blue,dark, :transaction_id FROM ml_adjust);
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            INSERT INTO 
                            gold_ledgers (gold, transaction_id)
                            VALUES 
                            (-1*(SELECT SUM(gold_ledgers.gold) FROM gold_ledgers)+100, :transaction_id);
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
    return "OK"