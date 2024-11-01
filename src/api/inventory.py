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
    capacity_numerator = 0
    capacity_denominator = 0
    numerator = 0
    denominator = 0
    cap = 0
    with db.engine.begin() as connection:
        sql_to_execute = "SELECT gold, ml_capacity FROM global_inventory"
        query = connection.execute(sqlalchemy.text(sql_to_execute))
        for result in query:
            usable_gold = result.gold
            capacity = result.ml_capacity

        sql_to_execute = "SELECT capacity_numerator, capacity_denominator, numerator, denominator, capacity_cap FROM parameters"
        query = connection.execute(sqlalchemy.text(sql_to_execute))
        for result in query:
            capacity_denominator = result.capacity_denominator
            capacity_numerator = result.capacity_numerator
            numerator = result.numerator
            denominator = result.denominator
            cap = result.capacity_cap

    cost_per_capacity = 1000
    both_capacity = 2 # Capacity is bought for both potions and ml at the same time
    capacity_desired = (capacity * capacity_numerator // capacity_denominator)
    capacity_desired_min = capacity_desired-capacity 
    capacity_buying = (numerator*usable_gold)//(both_capacity*cost_per_capacity*denominator)
    if capacity_buying < capacity_desired_min or capacity == cap:
        capacity_buying = 0
    if (capacity_buying + capacity) > cap:
        capacity_buying = cap-capacity
    print(f"Bought {capacity_buying} potion_capacity and {capacity_buying} ml_capacity")
    return {
        "potion_capacity": capacity_buying,
        "ml_capacity": capacity_buying
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
                "potion_capacity_added": potion_capacity_increment,
                "order_id":order_id
            }
        sql_to_execute = """
                        INSERT INTO transactions (description, time_id, order_id)
                        VALUES (
                            'Bought ' || :ml_capacity_added ||
                            ' ml _capacity ' || :potion_capacity_added ||
                            ' potion_capacity for ' || :gold_cost,
                            (SELECT MAX(time.id) FROM time LIMIT 1),
                            :order_id
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

if __name__ == "__main__":
    print("RAN Inventory.py")
    get_capacity_plan()

