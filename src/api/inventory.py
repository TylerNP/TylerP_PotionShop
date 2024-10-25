from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math

import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """
    Returns quantities of items in global inventory 
    """
    gold = 0
    ml_in_barrels = 0
    number_of_potions = 0
    with db.engine.begin() as connection:
        sql_to_execute = """
                            SELECT (num_red_ml+num_green_ml+num_blue_ml+num_dark_ml) AS ml_total, 
                            gold, ml_capacity, potion_capacity, (SELECT SUM(potions.quantity) FROM potions) AS num_potions
                            FROM global_inventory
                        """
        results = connection.execute(sqlalchemy.text(sql_to_execute))
        for result in results:
            gold = result.gold
            ml_in_barrels = result.ml_total
            number_of_potions = result.num_potions
    
    return {"number_of_potions": number_of_potions, "ml_in_barrels": ml_in_barrels, "gold": gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    usable_gold = 0
    with db.engine.begin() as connection:
        sql_to_execute = """
                            SELECT gold, ml_capacity, potion_capacity,
                            FROM global_inventory
                        """
            
        query = connection.execute(sqlalchemy.text(sql_to_execute))
        for result in query:
            thirds = 3
            two = 2
            usable_gold = (two * result.gold) // thirds
            ml_capacity = result.ml_capacity
            potion_capacity = result.potion_capacity

    cost_per_capacity = 1000
    potion_capacity_bought = 0
    ml_capacity_bought = 0

    # Only buy capacity to double storage 
    double = 2
    ml_capacity_desired = double * ml_capacity 
    potion_capacity_desired = ml_capacity_desired
    ml_capacity_bought = ml_capacity_desired - ml_capacity
    potion_capacity_bought = potion_capacity_desired - potion_capacity
    if usable_gold < cost_per_capacity*(ml_capacity_bought+potion_capacity_bought):
        ml_capacity_bought = 0
        potion_capacity_bought = 0
 
    print(f"Bought {potion_capacity_bought} potion_capacity and {ml_capacity_bought} ml_capacity")
    return {
        "potion_capacity": potion_capacity_bought,
        "ml_capacity": ml_capacity_bought
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    ml_capacity_increment = capacity_purchase.ml_capacity
    potion_capacity_increment = capacity_purchase.potion_capacity
    cost_per_capacity = 1000
    total_cost = cost_per_capacity*(ml_capacity_increment+potion_capacity_increment)
    with db.engine.begin() as connection:
        values = {
                "gold_cost": total_cost, 
                "ml_capacity_added":ml_capacity_increment, 
                "potion_capacity_added": potion_capacity_increment
            }
        sql_to_execute = """
                        INSERT INTO transactions (description, time_id)
                        VALUES (
                            'Bought ' || :ml_capacity_added ||
                            ' ml _capacity ' || :potion_capacity_added ||
                            ' potion_capacity for ' || :gold_cost,
                            (SELECT MAX(time.id) FROM time LIMIT 1)
                        ) 
                        RETURNING id
                    """
        values["transaction_id"] = connection.execute(sqlalchemy.text(sql_to_execute), values).scalar()
        sql_to_execute = """
                            INSERT INTO gold_ledgers (gold, transaction_id)
                            VALUES (:gold_cost, :transaction_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            UPDATE global_inventory 
                            SET gold = gold-:gold_cost,
                            ml_capacity = ml_capacity + :ml_capacity_added,
                            potion_capacity = potion_capacity + :potion_capacity_added
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)

    print(f"Used {total_cost} For {ml_capacity_increment} ml_capacity and {potion_capacity_increment} potion_capacity")
    return "OK"
